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


import os
import json
import argparse
from typing import Dict, List
from .client import VeupathRedmineClient
from .genome import Genome

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


def categorize_genome_issues(issues) -> Dict[str, List[Genome]]:
    validity: Dict[str, List[Genome]] = {
        'valid': [],
        'invalid': [],
    }
    operations: Dict[str, List[Genome]] = {}
    for issue in issues:
        genome = Genome(issue)
        genome.parse()

        if genome.errors:
            validity['invalid'].append(genome)
        else:
            validity['valid'].append(genome)
        
        for key in genome.operations:
            if key in operations:
                operations[key].append(genome)
            else:
                operations[key] = [genome]
    
    categories = {**validity, **operations}
    return categories


def summarize_genome_issues(issues) -> None:
    categories = categorize_genome_issues(issues)
    for key in categories:
        print(f"{len(categories[key])} {key}")


def check_genome_issues(issues) -> None:
    categories = categorize_genome_issues(issues)
    for key in categories:
        print(f"{len(categories[key])} {key}:")
        genomes = categories[key]
        for genome in genomes:
            print(genome.short_str())


def extract_genome_issues(issues, output_dir) -> None:

    group_names = {
        'Reference change': 'reference_change',
        'Load from RefSeq': 'new_genomes',
        'Load from INSDC': 'new_genomes',
        'Allocate stable ids': 'stable_ids',
        'Load from EnSEMBL': 'copy_ensembl',
        'Patch build': 'patch_build',
        'Other': 'other',
    }
    no_extraction = (
        'valid',
        'invalid',
    )

    categories = categorize_genome_issues(issues)
    for group, genomes in categories.items():
        if group in no_extraction:
            continue

        if genomes:
            if group in group_names:
                group_name = group_names[group]
            else:
                group_name = 'other'
            group_dir = os.path.join(output_dir, group_name)
            try:
                os.makedirs(group_dir)
            except FileExistsError:
                pass
            
            for genome in genomes:
                organism = genome.organism_abbrev
                organism_file = os.path.join(group_dir, organism + ".json")
                with open(organism_file, "w") as f:
                    json.dump(genome.to_json_struct(), f, indent=True)


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='List genome issues from Redmine')
    
    parser.add_argument('--key', type=str, required=True,
                        help='Redmine authentification key')
    # Choice
    parser.add_argument('--action',
                        choices=[
                            'check',
                            'summary',
                        ],
                        required=True,
                        help='What to do with the list of genome issues')
    # Optional
    parser.add_argument('--build', type=int,
                        help='Restrict to a given build')
    
    parser.add_argument('--output_dir', type=str,
                        help='Output_dir')
    args = parser.parse_args()
    
    # Start Redmine API
    redmine = VeupathRedmineClient(key=args.key)
    if args.build:
        redmine.set_build(args.build)

    issues = get_genome_issues(redmine)

    if args.action == "summary":
        summarize_genome_issues(issues)
    elif args.action == "check":
        check_genome_issues(issues)
    
    if args.output_dir:
        extract_genome_issues(issues, args.output_dir)


if __name__ == "__main__":
    main()
