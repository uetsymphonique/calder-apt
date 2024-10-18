from app.utility.base_world import BaseWorld

class OutputPrinting(BaseWorld):
    def __init__(self, output_file='results.txt'):
        super().__init__()
        self.output_file = output_file

    def print_output(self, output, verbose=True):
        if not self.output_file:
            print(output)
        else:
            with open(self.output_file, 'a') as f:
                if verbose:
                    f.write(output)

    def clear_file_content(self):
        with open(self.output_file, 'w') as f:
            pass

