# input: table file.csv
# output: table file.csv
import argparse
import csv

factor = 2
parser = argparse.ArgumentParser()
parser.add_argument('--in-table', required=True)
parser.add_argument('--out-table', required=True)
args = parser.parse_args()
with open(args.in_table, newline='', encoding='utf-8') as source:
    with open(args.out_table, 'w', newline='', encoding='utf-8') as destination:
        reader = csv.DictReader(source)
        writer = csv.writer(destination)
        writer.writerow(['value'])
        for row in reader:
            writer.writerow([float(row['value']) * factor])
