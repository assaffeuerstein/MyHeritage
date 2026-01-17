#!/usr/bin/env python3

import csv

# Read CSV file into list of dictionaries
with open('MyHeritage.csv', newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    data = [row for row in reader]

# Identify key fields for uniqueness
#key_fields = ['Name', 'Relationship', 'Birth date', 'Birth place', 'Death date', 'Death place']
#key_fields = ['Name', 'Relationship', 'Birth date', 'Death date']
key_fields = ['Name', 'Birth date', 'Death date']

# Create dictionary to store unique records
unique_data = {}

# Iterate through each record and check for duplicates
for record in data:
    key = tuple(record[field] for field in key_fields)
    if key in unique_data:
        print('Duplicate record:', record)
    else:
        unique_data[key] = record
