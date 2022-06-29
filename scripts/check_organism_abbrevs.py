#!env python3
# See the NOTICE file distributed with this work for additional information
# regarding copyright ownership.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import re
import argparse
from typing import Dict, List
from veupath.redmine.client import VeupathRedmineClient
from veupath.redmine.client.genome import Genome
from veupath.redmine.client.redmine_issue import RedmineIssue

supported_team = "Data Processing (EBI)"
supported_status_id = 20


def get_genome_issues(redmine: VeupathRedmineClient) -> list:
    """Get issues for all genomes"""

    redmine.add_filter("team", supported_team)

    genomes = []
    for datatype in Genome.supported_datatypes:
        redmine.add_filter("datatype", datatype)
        issues = redmine.get_issues()
        print(f"{len(issues)} issues for datatype '{datatype}'")
        genomes += issues
        redmine.remove_filter("datatype")
    print(f"{len(genomes)} issues for genomes")
    
    return genomes


def categorize_abbrevs(issues: List[RedmineIssue]) -> Dict[str, List[Genome]]:

    category: Dict[str, List[Genome]] = {
        "new": [],
        "valid": [],
        "invalid": []
    }
    for issue in issues:
        genome = Genome(issue)
        genome.parse()
        if genome.errors and not genome.organism_abbrev:
            new_org = _generate_abbrev(genome)
            genome.organism_abbrev = new_org
            category["new"].append(genome)
        else:
            valid = _validate_abbrev(genome.organism_abbrev)
            if valid:
                category["valid"].append(genome)
            else:
                category["invalid"].append(genome)
    
    return category


def check_abbrevs(issues: List[RedmineIssue]) -> None:
    categories = categorize_abbrevs(issues)

    for cat in ('invalid', 'new', 'valid'):
        cat_genomes = categories[cat]
        print(f"\n{len(cat_genomes)} {cat.upper()} organism abbrevs:")
        for genome in cat_genomes:
            new_org = genome.organism_abbrev
            line = [f"{new_org:20}", str(genome.issue.id)]
            line.append(f"From {genome.experimental_organism}")
            print("\t".join(line))


def update_abbrevs(redmine: VeupathRedmineClient, issues: List[RedmineIssue]) -> None:
    categories = categorize_abbrevs(issues)
    to_name = categories['new']
    print(f"\n{len(to_name)} new organism abbrevs to update:")
    for genome in to_name:
        new_org = genome.organism_abbrev
        line = [f"{new_org:20}", str(genome.issue.id)]
        status = redmine.update_custom_value(genome, 'Organism Abbreviation', new_org)
        if status:
            line.append("UPDATED")
        else:
            line.append("UPDATE FAILED")
        print("\t".join(line))


def _validate_abbrev(abbrev: str) -> bool:
    abbrev_format = r'^([a-z]{4}|[a-z]sp)[A-z0-9_.-]+$'
    if re.match(abbrev_format, abbrev):
        return True
    else:
        return False


def _generate_abbrev(genome) -> str:
    name = genome.experimental_organism
    
    name = name.strip()
    if name == "":
        raise Exception("field 'Experimental Organisms' needed")
    items = name.split(" ")
    if len(items) < 3:
        raise Exception(f"name is too short ({name})")

    genus = items[0]
    species = items[1]
    strain_abbrev = "".join(items[2:])
    
    genus = re.sub(r"[\[\]]", "", genus)
    strains_pattern = r"(isolate|strain|breed|str\.|subspecies|sp\.)"
    strain_abbrev = re.sub(strains_pattern, "", strain_abbrev, flags=re.IGNORECASE)
    strain_abbrev = re.sub(r"[\/\(\)#:-]", "", strain_abbrev)
    
    organism_abbrev = genus[0].lower() + species[0:3] + strain_abbrev
    return organism_abbrev


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='List and generate organism_abbrevs from Redmine')
    
    parser.add_argument('--key', type=str, required=True,
                        help='Redmine authentification key')

    parser.add_argument('--check', action='store_true', dest='check',
                        help='Show the organism_abbrev status for the selected issues')
    parser.add_argument('--update', action='store_true', dest='update',
                        help='Actually update the organism_abbrevs for the selected issues')

    # Optional
    parser.add_argument('--build', type=int,
                        help='Restrict to a given build')
    args = parser.parse_args()
    
    # Start Redmine API
    redmine = VeupathRedmineClient(key=args.key)
    if args.build:
        redmine.set_build(args.build)

    issues = get_genome_issues(redmine)

    if args.check:
        check_abbrevs(issues)
    elif args.update:
        update_abbrevs(redmine, issues)


if __name__ == "__main__":
    main()
