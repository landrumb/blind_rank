"""script which presents a CLI for comparing generations from a set of models to references"""

import argparse
import os
import sys
import pandas as pd
import random
import tty, termios


# Commands and escape codes
END_OF_TEXT = chr(3)  # CTRL+C (prints nothing)
END_OF_FILE = chr(4)  # CTRL+D (prints nothing)
CANCEL      = chr(24) # CTRL+X
ESCAPE      = chr(27) # Escape
CONTROL     = ESCAPE +'['
ENTER       = chr(0xD) # Enter

# Escape sequences for terminal keyboard navigation
ARROW_UP    = CONTROL+'A'
ARROW_DOWN  = CONTROL+'B'
ARROW_RIGHT = CONTROL+'C'
ARROW_LEFT  = CONTROL+'D'
KEY_END     = CONTROL+'F'
KEY_HOME    = CONTROL+'H'
PAGE_UP     = CONTROL+'5~'
PAGE_DOWN   = CONTROL+'6~'

# Escape sequences to match
commands = {
    ARROW_UP   :'up arrow',
    ARROW_DOWN :'down arrow',
    ARROW_RIGHT:'right arrow',
    ARROW_LEFT :'left arrow',
    KEY_END    :'end',
    KEY_HOME   :'home',
    PAGE_UP    :'page up',
    PAGE_DOWN  :'page down',
    ENTER      :'enter',
}

# Blocking read of one input character, detecting appropriate interrupts
def getch():
    k = sys.stdin.read(1)[0]
    if k in {END_OF_TEXT, END_OF_FILE, CANCEL}: raise KeyboardInterrupt
    # print('raw input 0x%X'%ord(k),end='\r\n')
    return k

# Println for raw terminal mode
def println(*args):
    print(*args,end='\r\n',flush=True)
# def println(*args):
#     print(*args)

# Preserve current terminal settings (we will restore these before exiting)
fd = sys.stdin.fileno()
old_settings = termios.tcgetattr(fd)

parser = argparse.ArgumentParser()

parser.add_argument("--output", type=str, default="rankings.csv", help="Output file name.")
parser.add_argument("--annotator", type=str, default="anonymous", help="Name of the annotator.")
parser.add_argument("--axis", type=str, default="overall", help="Axis ranking is performed on. Can be whatever property you want, although if there are multiple annotators you should agree on the name.")
parser.add_argument("-s", "--shuffle", action='store_true', help="Shuffle the order of the generations. Note that if you stop and come back, you could get an example you've already ranked in a previous session.")
parser.add_argument("-k", "--keep", action='store_true', help="Keep previous examples in the terminal.")
parser.add_argument("-b", "--beginning", action='store_true', help="Start from the beginning of the examples. This is applied automatically if --shuffle is passed.")

parser.add_argument("-c", "--csv", action='store_true', help="read from csv files instead of txt files. The csv files should each have a column named 'original' and a column named 'generation'.")
parser.add_argument("--input_dir", type=str, required=True, help="Directory to read input files from")
parser.add_argument("--prompt_filename", type=str, default="originals.txt", help="Name of the file containing the prompts/originals/inputs to the model. Not needed if --csv is passed.")

args = parser.parse_args()

# The example where the cursor is will be bolded, and if said example is being moved it will be blue
print("One generation from each model is presented below the original in initially random order. The 'cursor' can be moved up or down with the up and down arrow keys, and is indicated by the bolded example. The left and right arrow keys can be used to 'select' the bolded example, and when an example is selected (indicated by blue text), moving the cursor will also move the selected example. Once a ranking is completed, press enter to move on to the next example. To exit and save your annotations, press ctrl+c.")

LINE_UP = '\033[1A'
LINE_CLEAR = '\x1b[2K'

RED_TEXT = '\033[91m'
GREEN_TEXT = '\033[92m'
BLUE_TEXT = '\033[96m'
BOLD_TEXT = '\033[1m'
END_COLOR = '\033[0m'

SELECTED_COLOR = RED_TEXT

models = [short[:-4] for short in os.listdir(args.input_dir)]
if args.csv:
    dfs = {short: pd.read_csv(os.path.join('/nfshomes/landrum/keep_it_formal/eval/best_outputs', f'{short}.csv')) for short in models}

    generations = pd.DataFrame({'original': dfs[models[0]]['original']} | {short: dfs[short]['generation'] for short in models})
else:
    with open(os.path.join(args.input_dir, args.prompt_filename)) as f:
        originals = f.readlines()

    generations = pd.DataFrame({'original': originals} | {short: [line.strip() for line in open(os.path.join(args.input_dir, f'{short}.txt'))] for short in models})



class Printer:
    def __init__(self):
        self.lines = 0

    def print(self, string):
        println(string)
        self.lines += string.count('\n') + 1

    def clear(self):
        for _ in range(self.lines):
            print(LINE_UP + LINE_CLEAR, end='', flush=True)
        self.lines = 0

    def replace(self, string):
        self.clear()
        self.print(string)

    def add_lines(self, n=1):
        self.lines += n

    # def __del__(self):
    #     self.clear()

class Ranker(Printer):
    """a class which contains functionality for ranking a set of strings"""
    def __init__(self, strings, labels=None, allow_ties=False):
        """preserves the order of the passed strings as the initial ranking if no labels are passed"""
        super().__init__()
        self.elements = [(x, y) for x, y in zip(labels if labels else range(1, len(strings) + 1), strings)]
        if labels:
            random.shuffle(self.elements)

        self.active_index = 0
        self.selected = False
        self.print_ranking()

    def _swap(self, i, j):
        tmp = self.elements[i]
        self.elements[i] = self.elements[j]
        self.elements[j] = tmp

    def print_ranking(self):
        output = '\r'
        for i, (_, string) in enumerate(self.elements):
            if i == self.active_index:
                output += BOLD_TEXT
            output += f"{i+1}: "
            if i == self.active_index and self.selected:
                output += SELECTED_COLOR
            output += string + END_COLOR + '\r\n'
                
        self.replace(output)

    def move_up(self):
        if self.active_index == 0:
            return
        if self.selected:
            self._swap(self.active_index, self.active_index - 1)
        self.active_index -= 1
        self.print_ranking()

    def move_down(self):
        if self.active_index == len(self.elements) - 1:
            return
        if self.selected:
            self._swap(self.active_index, self.active_index + 1)
        self.active_index += 1
        self.print_ranking()

    def select(self):
        self.selected = not self.selected
        self.print_ranking()

        

p = Printer()

output_filename = args.output if args.output.endswith('.csv') else args.output + '.csv'

if os.path.exists(output_filename):
    rankings = pd.read_csv(output_filename, index_col=0)
    initial_length = len(rankings) # to detect concurrent editing
    if 'annotator' in rankings.columns:
        start_index = len(rankings[rankings['annotator'] == args.annotator])
    else:
        start_index = 0

else:
    rankings = pd.DataFrame()
    start_index = 0

if args.beginning or args.shuffle:
    start_index = 0

rankings.index.name = 'index'

rows = list(generations.iterrows())
if args.shuffle:
    random.shuffle(rows)

try:
    # Enter raw mode (key events sent directly as characters)
    tty.setraw(sys.stdin.fileno())

    for i, (row_index, row) in enumerate(rows[start_index:]):
        p.replace(f'{i + 1 + start_index}/{len(rows)}')
        p.print(f"Original: {row['original'].strip()}")

        # get a list of the generations for the row
        generations = [row[model].strip() for model in models]
        
        ranking = Ranker(generations, labels=models)

        # ranking.move_down()
        ranking.select()
        # ranking.print_ranking()

        while True:
            read = getch()
            while any(k.startswith(read) for k in commands.keys()): 
                if read in commands: 
                    # println(f"command: {commands[read]}")
                    cmd = commands[read]
                    read = ''
                    break
                read += getch()
            # println("escaped")
            if cmd == 'enter':
                break
            elif cmd == 'up arrow':
                # println("arrow up")
                ranking.move_up()
            elif cmd == 'down arrow':
                # println("arrow down")
                ranking.move_down()
            elif cmd == 'right arrow' or cmd == 'left arrow':
                # println("arrow right/left")
                ranking.select()

        # add the ranking to the dataframe
        labels = [label for label, _ in ranking.elements]
        ranking_row = {f"{model}_ranking":labels.index(model) + 1 for model in models}
        rankings = pd.concat([rankings, pd.DataFrame({'original': row['original'].strip(), 'annotator': args.annotator} | ranking_row, index=[row_index])])

        if args.keep:
            p.add_lines(-1)
        else:
            ranking.clear()
            # p.add_lines(6)

finally:
    # Restore normal keyboard mode
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings) 

    # if someone else is concurrently ranking generations in the same directory, we don't want this to cause overwriting of one or the other set of annotations.
    # so we read in the current output file again, check if it's longer than when we started, and if so, we append our annotations to the new file.
    if os.path.exists(output_filename):
        external_rankings = pd.read_csv(output_filename, index_col=0)
        if len(external_rankings) > initial_length and len(rankings) > initial_length:
            rankings = pd.concat([external_rankings, rankings[initial_length:]])

    if len(rankings) > 0:
        rankings.to_csv(output_filename, index=True)

    print(f'Annotated {len(rankings) - start_index} examples.')
    # print(rankings)

    # print('')
    sys.exit(0)
