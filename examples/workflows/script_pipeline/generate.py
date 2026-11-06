# output: table file.csv
import argparse
import csv

rows = 5
parser = argparse.ArgumentParser()
parser.add_argument('--out-table', required=True)
args = parser.parse_args()
with open(args.out_table, 'w', newline='', encoding='utf-8') as handle:
    writer = csv.writer(handle)
    writer.writerow(['value'])
    writer.writerows([index] for index in range(1, rows + 1))
