import argparse
import asyncio
import glob
import logging
import os
import sys
# import app
# import plugins.atomic.app
# import plugins.emu.app
# import plugins.manx.app
# import plugins.sandcat.app
# import plugins.stockpile.app

from aiohttp import web
from colorama import init, Fore
from prettytable import PrettyTable

from app.api.rest_api import RestApi
from app.ascii_banner import ASCII_BANNER, print_rich_banner
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
from app.utility.output_printing import OutputPrinting
from app.utility.resources_path import resource_path

init(autoreset=True)


def setup_logger(level=logging.DEBUG):
    logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s', filename='program.log')
    format = "%(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    # if no_color():
    #     logging.basicConfig(level=level, format=format, datefmt=datefmt)
    # else:
    #     console = Console(theme=Theme({"logging.level.warning": "yellow"}))
    #     logging.basicConfig(
    #         level=level,
    #         format=format,
    #         datefmt=datefmt,
    #         handlers=[RichHandler(rich_tracebacks=True, markup=True, console=console)]
    #     )

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

            await data_svc.load_ability_file(ability_file, access=BaseWorld.Access.RED)

    adversary = data_svc.ram["adversaries"][0]
    source = data_svc.ram["sources"][0]
    planner = data_svc.ram["planners"][0]
    operation = Operation(
        adversary=adversary,
        planner=planner,
        source=source,
        name=adversary.name,
        auto_close=False
    )
    await data_svc.store(operation)


async def run_operation(data_svc):
    operation = data_svc.ram["operations"][0]
    print(
        f'\r{Fore.CYAN}############# ADVERSARY PLAN: {operation.adversary.name} - planner: {operation.planner.name} #############\n'
        f'{Fore.CYAN}OPERATION: {operation.name} - fact: {operation.source.name} (run with obfuscator: {operation.obfuscator})\n')
    choices = ['Run operation', 'Stop operation', 'Show agents', 'Operation details', 'Exit']
    while True:
        choice_str = "\n".join([f'[{index}] {choice}' for index, choice in enumerate(choices)])
        print(f'{Fore.CYAN}{choice_str}\nEnter your choice: ', end='', flush=True)
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, sys.stdin.readline)
        if response.strip() == '0':
            loop.create_task(operation.run(app_svc.get_services()))
        elif response.strip() == '1':
            operation.state = 'finished'
        elif response.strip() == '2':
            agents = [a.display for a in await data_svc.locate('agents')]
            table = PrettyTable()
            table.field_names = ['id', 'display_name', 'group', 'platform', 'contact', 'privilege']
            for agent in agents:
                table.add_row([agent["paw"], agent["display_name"], agent["group"], agent["platform"], agent["contact"],
                               agent["privilege"]])
            print(f'{Fore.YELLOW}{table}')
        elif response.strip() == '3':
            def get_key_by_value(target_value):
                states = dict(HIGH_VIZ=-5,
                              UNTRUSTED=-4,
                              EXECUTE=-3,
                              DISCARD=-2,
                              PAUSE=-1,
                              SUCCESS=0,
                              ERROR=1,
                              TIMEOUT=124)
                for key, value in states.items():
                    if value == int(target_value):
                        return str(key.lower())
                return 'undefined'

            table = PrettyTable()
            table.field_names = ['Time Ran', 'Status', 'Ability', 'Tactic', 'Agent', 'Host']

            for link in operation.chain:
                table.add_row([link.decide, get_key_by_value(link.display["status"]),
                               link.ability.name + (' (cleanup)' if link.cleanup else ''), link.ability.tactic, link.paw,
                               link.host])
            print(f'{Fore.YELLOW}Operation details:\n{table}')
        elif response.strip() == str(len(choices) - 1):
            break


def run_tasks(services):
    loop = asyncio.get_event_loop()
    # loop.create_task(app_svc.validate_requirements())
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
    # loop.create_task(app_svc.start_sniffer_untrusted_agents())
    # loop.create_task(app_svc.resume_operations())
    # loop.create_task(app_svc.run_scheduler())
    loop.create_task(learning_svc.build_model())
    loop.create_task(app_svc.watch_ability_files())
    loop.run_until_complete(start_server())
    loop.run_until_complete(event_svc.fire_event(exchange="system", queue="ready"))
    loop.create_task(run_operation(data_svc))
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
    parser.add_argument(
        "-w",
        "--write-file",
        action="store_true",
        dest="write_file",
        help="Write output to a file",
    )

    def list_str(values):
        return values.split(",")

    # def get_plugins_path():
    #     if getattr(sys, 'frozen', False):
    #         base_path = sys._MEIPASS
    #     else:
    #         base_path = os.path.abspath(".")
    #
    #     return os.path.join(base_path, "plugins")

    parser.add_argument(
        "-P",
        "--plugins",
        required=False,
        default=os.listdir('plugins'),
        help="Start up with a single plugin",
        type=list_str,
    )
    return parser


if __name__ == "__main__":
    sys.path.append("")
    OutputPrinting('program.log').clear_file_content()
    OutputPrinting('results.txt').clear_file_content()

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
    contact_svc = ContactService(write_file=args.write_file)
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
