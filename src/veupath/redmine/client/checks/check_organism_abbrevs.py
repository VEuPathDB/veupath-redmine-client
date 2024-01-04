#!/usr/bin/env python
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
from os import PathLike
from pathlib import Path
from typing import Dict, List, Optional

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


def categorize_abbrevs(
    issues: List[RedmineIssue], cur_abbrevs_path: Optional[PathLike]
) -> Dict[str, List[Genome]]:
    cur_abbrevs = OrgsUtils.load_abbrevs(cur_abbrevs_path)
    category: Dict[str, List[Genome]] = {
        "set_new": [],
        "set_replacement": [],
        "to_update": [],
        "invalid": [],
        "duplicate": [],
        "used_abbrev": [],
        "unknown_replacement": [],
    }

    previous_names = set()
    for issue in issues:
        genome = Genome(issue)
        genome.parse()
        new_abbrev = False
        valid_abbrev = False
        used_abbrev = False
        duplicate = False

        # Create new organism abbrev if necessary
        if not genome.organism_abbrev:
            exp_organism = genome.experimental_organism
            new_org = OrgsUtils.generate_abbrev(exp_organism)
            genome.organism_abbrev = new_org
            new_abbrev = True

        # Check that the format of the abbrev is valid
        try:
            OrgsUtils.validate_abbrev(genome.organism_abbrev)
            valid_abbrev = True
        except InvalidAbbrev:
            valid_abbrev = False

        # Check if the abbrev is already in use
        if genome.organism_abbrev.lower() in cur_abbrevs:
            used_abbrev = True

        if genome.organism_abbrev in previous_names:
            duplicate = True
        else:
            previous_names.update([genome.organism_abbrev])

        # Categorize
        if not valid_abbrev:
            category["invalid"].append(genome)
        elif duplicate:
            category["duplicate"].append(genome)
        else:
            if used_abbrev:
                if genome.is_replacement:
                    if new_abbrev:
                        category["to_update"].append(genome)
                    else:
                        category["set_replacement"].append(genome)
                else:
                    category["used_abbrev"].append(genome)
            else:
                if genome.is_replacement:
                    category["unknown_replacement"].append(genome)
                else:
                    if new_abbrev:
                        category["to_update"].append(genome)
                    else:
                        category["set_new"].append(genome)

    return category


def check_abbrevs(issues: List[RedmineIssue], cur_abbrevs_path: Optional[PathLike]) -> None:
    categories = categorize_abbrevs(issues, cur_abbrevs_path)
    
    cats = {
            "invalid": "WARNING: the format of the abbrev is not valid",
            "duplicate": "WARNING: several tickets use the same abbrev",
            "used_abbrev": "WARNING: abbrev is set in the ticket and known, check that the operation needs a known abbrev",
            "unknown_replacement": "WARNING: abbrev is set in the ticket and new, not expected for a replacement",
            "set_new": "OK: abbrev is already set in the ticket and is new",
            "set_replacement": "OK: abbrev is set in the ticket and is known, expected for a replacement",
            "to_update": "TODO: add --update to generate the organism_abbrev and update the tickets",
    }

    for cat, description in cats.items():
        cat_genomes = categories[cat]
        if len(cat_genomes) == 0:
            continue
        print(f"\n{len(cat_genomes)} {cat.upper()} organism abbrevs\n\t{description}:")
        for genome in cat_genomes:
            new_org = genome.organism_abbrev
            line = [f"{new_org:20}", str(genome.issue.id)]
            line.append(f"({', '.join(genome.operations)})")
            line.append(f"From {genome.experimental_organism}")
            print("\t".join(line))


def update_abbrevs(
    redmine: VeupathRedmineClient, issues: List[RedmineIssue], cur_abbrevs_path: Optional[PathLike]
) -> None:
    categories = categorize_abbrevs(issues, cur_abbrevs_path)
    to_name = categories["to_update"]
    print(f"\n{len(to_name)} new organism abbrevs to update:")
    for genome in to_name:
        new_org = genome.organism_abbrev
        line = [f"{new_org:20}", str(genome.issue.id)]
        status = redmine.update_custom_value(genome, "Organism Abbreviation", new_org)
        if status:
            line.append("UPDATED")
        else:
            line.append("UPDATE FAILED")
        print("\t".join(line))


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="List and generate organism_abbrevs from Redmine")

    parser.add_argument("--key", type=str, help="Redmine authentication key")

    parser.add_argument(
        "--check",
        action="store_true",
        dest="check",
        help="Show the organism_abbrev status for the selected issues",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        dest="update",
        help="Actually update the organism_abbrevs for the selected issues",
    )

    # Optional
    parser.add_argument("--build", type=int, help="Restrict to a given build")

    parser.add_argument(
        "--current_abbrevs", type=str, required=False, help="Path to a list of current abbrevs"
    )

    parser.add_argument("--validate", type=str, help="Check the validity of one abbreviation")
    parser.add_argument("--generate_abbrev", type=str, help="Generate an abbrev from a species full name")

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
        current_abbrevs = Path(args.current_abbrevs)

        if args.check:
            check_abbrevs(issues, current_abbrevs)
        elif args.update:
            update_abbrevs(redmine, issues, current_abbrevs)


if __name__ == "__main__":
    main()
