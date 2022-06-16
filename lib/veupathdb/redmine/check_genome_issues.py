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


def report_genome_issues(issues, report: str) -> None:
    categories = categorize_genome_issues(issues)
    all_issues: List[Genome] = categories['valid']

    new_genomes_operations = ("Load from INSDC", "Load from RefSeq", "Load from EnsEMBL")

    new_genomes: List[Genome] = []
    others: List[Genome] = []

    for issue in all_issues:
        is_new_genome = False
        for op in issue.operations:
            if op in new_genomes_operations:
                is_new_genome = True
        
        if is_new_genome:
            new_genomes.append(issue)
        else:
            others.append(issue)
    
    components = {}
    for issue in new_genomes:
        comp = issue.component
        
        if comp not in components:
            components[comp] = [issue]
        else:
            components[comp].append(issue)

    lines = []
    lines.append(f"{len(all_issues)} genomes handed over:")
    lines.append(f"- {len(new_genomes)} new genomes:")
    for comp, issues in components.items():
        lines.append(f"\t- {len(issues)} {comp}")

    lines.append(f"- {len(others)} other operations:")
    for issue in others:
        lines.append(f"\t- {issue.organism_abbrev}: {', '.join(issue.operations)}")
    lines.append("")

    for comp, issues in components.items():
        lines.append(f"{comp}")
        lines.append(f"{len(issues)} new genomes:")
        for issue in issues:
            lines.append(f"- {issue.organism_abbrev} ({issue.accession})")
        lines.append("")

    with open(report, "w") as report_fh:
        report_fh.write("\n".join(lines))


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

    parser.add_argument('--check', action='store_true', dest='check',
                        help='Parse issues and report errors')
    parser.add_argument('--summary', action='store_true', dest='summary',
                        help='Short count of all categories')
    parser.add_argument('--report', type=str,
                        help='Write a report to a file')
    parser.add_argument('--store', type=str,
                        help='Write json files for each Redmine issue')

    # Optional
    parser.add_argument('--build', type=int,
                        help='Restrict to a given build')
    args = parser.parse_args()
    
    # Start Redmine API
    redmine = VeupathRedmineClient(key=args.key)
    if args.build:
        redmine.set_build(args.build)

    issues = get_genome_issues(redmine)

    if args.summary:
        summarize_genome_issues(issues)
    elif args.check:
        check_genome_issues(issues)
    elif args.report:
        report_genome_issues(issues, args.report)
    elif args.store:
        extract_genome_issues(issues, args.store)


if __name__ == "__main__":
    main()
