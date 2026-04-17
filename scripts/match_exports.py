import csv
import argparse
import collections

MATCH_DISTRICTS = ['HI-1', 'ME-2', 'FL-7', 'NY-4', 'OR-5']
ZIPCODES_LOOKUP = collections.defaultdict(list)

EXPORT = []

def main(loadfile):
    zipcodes = {}
    # load list of us_districts
    with open('us_districts.csv') as zipcodes_file:
        zipcodes = csv.DictReader(zipcodes_file)
        for z in zipcodes:
            # make faster lookup dict of lists
            ZIPCODES_LOOKUP[z['zcta']].append({'state': z['state_abbr'], 'cd': z['cd']})
    print(f'loaded {len(ZIPCODES_LOOKUP)} zips')

    # load campaign export csv
    with open(loadfile) as csvfile:
        calls = csv.reader(csvfile)

        # check each entry for district match by zipcode
        for row in calls:
            # print(row)
            call_lookup = ZIPCODES_LOOKUP.get(row[1])
            if not call_lookup:
                print(f'unable to match {row[1]}')
                continue
            for z in call_lookup:
                for m in MATCH_DISTRICTS:
                    match_state, match_cd = m.split('-')
                    if z['state'] == match_state and z['cd'] == match_cd:
                        matched_row = {
                            'phone': row[0],
                            'zip': row[1],
                            'state': z['state'],
                            'cd': z['cd']
                        }
                        EXPORT.append(matched_row)

    print(f'got {len(EXPORT)} matches')

    # only export matches
    with open('matched_calls.csv', 'w') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=['phone','zip','state','cd'])
        writer.writeheader()
        for row in EXPORT:
            writer.writerow(row)
        print('done')

if __name__=="__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Match CallPower campaign export to specific districts')
    parser.add_argument('filename', help='CSV file to load')
    args = parser.parse_args()

    main(args.filename)