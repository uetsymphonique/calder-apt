import argparse
import asyncio
import glob
import logging
import os
import sys

from aiohttp import web
from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

from app.api.rest_api import RestApi
from app.ascii_banner import ASCII_BANNER, no_color, print_rich_banner
from app.objects.c_agent import Agent
from app.objects.c_objective import Objective
from app.objects.c_operation import Operation
from app.objects.secondclass.c_executor import Executor
from app.objects.secondclass.c_goal import Goal
from app.objects.secondclass.c_link import Link
from app.service.app_svc import AppService
from app.service.contact_svc import ContactService
from app.service.data_svc import DataService
from app.service.event_svc import EventService
from app.service.file_svc import FileSvc
from app.service.knowledge_svc import KnowledgeService
from app.service.learning_svc import LearningService
from app.service.planning_svc import PlanningService
from app.service.rest_svc import RestService
from app.utility.base_object import AppConfigGlobalVariableIdentifier
from app.utility.base_world import BaseWorld


def setup_logger(level=logging.DEBUG):
    format = "%(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    if no_color():
        logging.basicConfig(level=level, format=format, datefmt=datefmt)
    else:
        console = Console(theme=Theme({"logging.level.warning": "yellow"}))
        logging.basicConfig(
            level=level,
            format=format,
            datefmt=datefmt,
            handlers=[RichHandler(rich_tracebacks=True, markup=True, console=console)]
        )

    for logger_name in logging.root.manager.loggerDict.keys():
        if logger_name in ("aiohttp.server", "asyncio"):
            continue
        else:
            logging.getLogger(logger_name).setLevel(100)
    logging.getLogger("markdown_it").setLevel(logging.WARNING)
    logging.captureWarnings(True)


async def start_server():
    runner = web.AppRunner(app_svc.application)
    await runner.setup()
    await web.TCPSite(
        runner, BaseWorld.get_config("host"), BaseWorld.get_config("port")
    ).start()


async def load_data(data_svc):
    await data_svc.load_adversary_file('data/adversary.yml', access=BaseWorld.Access.RED)
    await data_svc.load_source_file('data/source.yml', access=BaseWorld.Access.RED)
    # await data_svc.load_objective_file('data/objective.yml')
    await data_svc.load_planner_file('data/planner.yml', access=BaseWorld.Access.RED)
    await data_svc.store(
        Objective(id='495a9828-cab1-44dd-a0ca-66e58177d8cc', name='default', goals=[Goal()])
    )
    for abilities_folder in glob.glob('data/abilities/*'):
        for ability_file in glob.glob(f'{abilities_folder}/*'):
            # print(f, type(f))
            await data_svc.load_ability_file(ability_file, access=BaseWorld.Access.RED)
    adversary = data_svc.ram["adversaries"][0]
    source = data_svc.ram["sources"][0]
    planner = data_svc.ram["planners"][0]
    # agent = Agent(executors=args.executors.split(", "))
    await data_svc.store(
        Operation(
            adversary=adversary,
            planner=planner,
            source=source,
            name=adversary.name
        )
    )


def run_tasks(services):
    loop = asyncio.get_event_loop()
    loop.create_task(app_svc.validate_requirements())
    loop.run_until_complete(app_svc.register_contacts())
    loop.run_until_complete(app_svc.load_plugins(args.plugins))
    loop.run_until_complete(load_data(data_svc))
    loop.run_until_complete(
        data_svc.load_data(
            loop.run_until_complete(data_svc.locate("plugins", dict(enabled=True)))
        )
    )
    loop.run_until_complete(
        app_svc.load_plugin_expansions(
            loop.run_until_complete(data_svc.locate("plugins", dict(enabled=True)))
        )
    )
    loop.run_until_complete(RestApi(services).enable())
    loop.create_task(app_svc.start_sniffer_untrusted_agents())
    loop.create_task(app_svc.resume_operations())
    loop.create_task(app_svc.run_scheduler())
    loop.create_task(learning_svc.build_model())
    loop.create_task(app_svc.watch_ability_files())
    loop.run_until_complete(start_server())
    loop.run_until_complete(event_svc.fire_event(exchange="system", queue="ready"))
    try:
        logging.info("All systems ready.")
        print_rich_banner()
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(
            services.get("app_svc").teardown()
        )


def _get_parser():
    parser = argparse.ArgumentParser(
        description=ASCII_BANNER,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "-l",
        "--log",
        dest="logLevel",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level",
        default="INFO",
    )

    def list_str(values):
        return values.split(",")

    parser.add_argument(
        "-P",
        "--plugins",
        required=False,
        default=os.listdir("plugins"),
        help="Start up with a single plugin",
        type=list_str,
    )
    return parser


if __name__ == "__main__":
    sys.path.append("")

    parser = _get_parser()
    args = parser.parse_args()
    setup_logger(getattr(logging, args.logLevel))

    main_config_path = "conf/default.yml"
    BaseWorld.apply_config("main", BaseWorld.strip_yml(main_config_path)[0])
    logging.debug("Using main config from %s" % main_config_path)
    BaseWorld.apply_config("agents", BaseWorld.strip_yml("conf/agents.yml")[0])
    BaseWorld.apply_config("payloads", BaseWorld.strip_yml("conf/payloads.yml")[0])
    data_svc = DataService()
    knowledge_svc = KnowledgeService()
    contact_svc = ContactService()
    planning_svc = PlanningService(
        global_variable_owners=[
            Executor,
            Agent,
            Link,
            AppConfigGlobalVariableIdentifier,
        ]
    )
    rest_svc = RestService()
    file_svc = FileSvc()
    learning_svc = LearningService()
    event_svc = EventService()

    app_svc = AppService(
        application=web.Application(
            client_max_size=5120 ** 2
        )
    )

    run_tasks(services=app_svc.get_services())
