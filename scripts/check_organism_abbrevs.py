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


import argparse
from typing import Dict, List
from veupath.redmine.client import VeupathRedmineClient
from veupath.redmine.client.genome import Genome
from veupath.redmine.client.redmine_issue import RedmineIssue
from veupath.redmine.client.orgs_utils import InvalidAbbrev, InvalidOrganism, OrgsUtils

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


def categorize_abbrevs(issues: List[RedmineIssue],
                       cur_abbrevs_path: str = "") -> Dict[str, List[Genome]]:

    cur_abbrevs = OrgsUtils.load_abbrevs(cur_abbrevs_path)
    category: Dict[str, List[Genome]] = {
        "new": [],
        "valid": [],
        "invalid": [],
        "exists_replace": [],
        "exists_noreplace": [],
        "new_exists_replace": [],
        "new_exists_noreplace": [],
    }

    for issue in issues:
        genome = Genome(issue)
        genome.parse()
        if not genome.organism_abbrev:
            exp_organism = genome.experimental_organism
            new_org = OrgsUtils.generate_abbrev(exp_organism)
            genome.organism_abbrev = new_org
            if new_org.lower() in cur_abbrevs:
                if genome.is_replacement:
                    category["new_exists_replace"].append(genome)
                else:
                    category["new_exists_noreplace"].append(genome)
            else:
                category["new"].append(genome)
                cur_abbrevs.update([new_org])
        else:
            if genome.organism_abbrev.lower() in cur_abbrevs:
                if genome.is_replacement:
                    category["exists_replace"].append(genome)
                else:
                    category["exists_noreplace"].append(genome)
            else:
                cur_abbrevs.update([genome.organism_abbrev])
                try:
                    OrgsUtils.validate_abbrev(genome.organism_abbrev)
                    category["valid"].append(genome)
                except InvalidAbbrev:
                    category["invalid"].append(genome)
    
    return category


def check_abbrevs(issues: List[RedmineIssue], cur_abbrevs_path: str) -> None:
    categories = categorize_abbrevs(issues, cur_abbrevs_path)

    for cat in (
        'invalid',
        'new_exists_replace',
        'new_exists_noreplace',
        'exists_noreplace',
        'new',
        'exists_replace',
        'valid',
    ):
        cat_genomes = categories[cat]
        if len(cat_genomes) == 0:
            continue
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


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='List and generate organism_abbrevs from Redmine')
    
    parser.add_argument('--key', type=str,
                        help='Redmine authentification key')

    parser.add_argument('--check', action='store_true', dest='check',
                        help='Show the organism_abbrev status for the selected issues')
    parser.add_argument('--update', action='store_true', dest='update',
                        help='Actually update the organism_abbrevs for the selected issues')

    # Optional
    parser.add_argument('--build', type=int,
                        help='Restrict to a given build')
    
    parser.add_argument('--current_abbrevs', type=str, required=False,
                        help='Path to a list of current abbrevs')

    parser.add_argument('--validate', type=str,
                        help='Check the validity of one abbreviation')
    parser.add_argument('--generate_abbrev', type=str,
                        help='Generate an abbrev from a species full name')

    args = parser.parse_args()
    
    if args.validate:
        try:
            OrgsUtils.validate_abbrev(args.validate)
            print("Abbrev is valid")
        except InvalidAbbrev as ex:
            print(ex)

    elif args.generate_abbrev:
        try:
            abbrev = OrgsUtils.generate_abbrev(args.generate_abbrev)
            print(f"Abbrev for '{args.generate_abbrev}' is '{abbrev}'")
        except InvalidOrganism as ex:
            print(ex)

    else:
        if not args.key:
            print("Key needed")
            return

        # Start Redmine API
        redmine = VeupathRedmineClient(key=args.key)
        if args.build:
            redmine.set_build(args.build)

        issues = get_genome_issues(redmine)

        if args.check:
            check_abbrevs(issues, args.current_abbrevs)
        elif args.update:
            update_abbrevs(redmine, issues)


if __name__ == "__main__":
    main()
