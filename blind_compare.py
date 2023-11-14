"""
This script predates the ranking one, and is not currently as polished.

script which presents a CLI for comparing generations from a set of models to references"""

import argparse
import os
import sys
import pandas as pd
import random

parser = argparse.ArgumentParser()

parser.add_argument("--output", type=str, default="annotations.csv", help="Output file name.")
parser.add_argument("-s", "--shuffle", action='store_true', help="Shuffle the order of the generations.")
parser.add_argument("-a", "--append", action='store_true', help="Append to the output file instead of overwriting it.")

args = parser.parse_args()

print("To label a generation as having a given property, type the corresponding letter (or a combination of letters representing properties) and press enter. For example, to label a generation as fluent and consistent, type 'fc' and press enter. To remove a label, type the same letter again and press enter. To move to the next generation, press enter without typing anything. To exit, press ctrl+c.")

LINE_UP = '\033[1A'
LINE_CLEAR = '\x1b[2K'

RED_TEXT = '\033[91m'
GREEN_TEXT = '\033[92m'
END_COLOR = '\033[0m'

PROPERTIES = {'f': 'fluent', 'c': 'consistent', 'b': 'believable', 'm':'more formal', 's': 'superficial', 'x':'exact copy', 'r':'has bad replacements'}

models = ['random_golden', 'nmt_baseline', '3shot-prompts', 'c2_f6_rb_ucg-cis_nli-g_12h', 'rule_based']

dfs = {short: pd.read_csv(os.path.join('/fs/clip-scratch/landrum/keep_it_formal/eval/best_outputs', f'{short}_best.csv')) for short in models}

generations = pd.DataFrame({'original': dfs['random_golden']['original']} | {short: dfs[short]['generation'] for short in models})

# print(generations.head())

class Printer:
    def __init__(self):
        self.lines = 0

    def print(self, string):
        print(string)
        self.lines += string.count('\n') + 1

    def clear(self):
        for _ in range(self.lines):
            print(LINE_UP + LINE_CLEAR, end='')
        self.lines = 0

    def replace(self, string):
        self.clear()
        self.print(string)

    def add_lines(self, n=1):
        self.lines += n

    # def __del__(self):
    #     self.clear()

p = Printer()

if os.path.exists(args.output) or not args.append:
    annotations = pd.read_csv(args.output, index_col=0)
else:
    annotations = pd.DataFrame(columns=['original', 'generation', 'model'] + list(PROPERTIES.values()))

rows = list(generations.iterrows())
if args.shuffle:
    random.shuffle(rows)

for i, (row_index, row) in enumerate(rows):
    p.replace(f'{i+1}/{len(generations)}')
    p.print(f"Original:\t{row['original'].strip()}")

    # choose a random model to be the displayed generation
    model = random.choice(models)
    p.print(f"Generation:\t{row[model].strip()}")
    
    # get user input and display it
    user_input = {short : False for short in PROPERTIES.keys()}
    display = Printer()

    while True:
        instructions = "Is this generation "
        for short, prop in PROPERTIES.items():
            instructions += GREEN_TEXT if user_input[short] else RED_TEXT
            instructions += f"{prop} ({short}){END_COLOR}, "
        instructions = instructions[:-2] + "?"
        display.replace(instructions)

        try:
            inp = input()
        except KeyboardInterrupt:
            annotations.to_csv(args.output, index=True)
            print()
            sys.exit(0)
        except EOFError:
            print("eof error")
            break

        display.add_lines()
        
        if inp == '':
            print("empty input")
            break
        for short in PROPERTIES.keys():
            if short in inp:
                user_input[short] = not user_input[short]

    display.clear()

    # add the annotations to the dataframe
    user_input = {prop: user_input[short] for short, prop in PROPERTIES.items()}
    annotations = pd.concat([annotations, 
                             pd.DataFrame({'original': row['original'].strip(), 'generation': row[model].strip(), 'model': model, **user_input}, index=[row_index])])
    
    # clear the display
    p.add_lines()
    p.clear()
