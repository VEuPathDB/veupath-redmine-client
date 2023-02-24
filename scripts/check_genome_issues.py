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
from Bio import Entrez
from veupath.redmine.client import VeupathRedmineClient
from veupath.redmine.client.genome import Genome

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
        for issue in issues:
            genome = Genome(issue)
            genome.parse()

            genomes.append(genome)
        redmine.remove_filter("datatype")
    print(f"{len(genomes)} issues for genomes")
    
    return genomes


def categorize_genome_issues(genomes, check_gff=False) -> Dict[str, List[Genome]]:
    validity: Dict[str, List[Genome]] = {
        'valid': [],
        'invalid': [],
    }
    operations: Dict[str, List[Genome]] = {}
    for genome in genomes:
        if genome.errors:
            validity['invalid'].append(genome)
        else:
            validity['valid'].append(genome)
        
        if genome.gff:
            gff_operation = "Load from GFF"
            if gff_operation in operations:
                operations[gff_operation].append(genome)
            else:
                operations[gff_operation] = [genome]

        if genome.is_replacement:
            rep_operation = "Replacement"
            if rep_operation in operations:
                operations[rep_operation].append(genome)
            else:
                operations[rep_operation] = [genome]

        for key in genome.operations:
            if genome.gff and key in ("Load from INSDC", "Load from RefSeq"):
                continue

            if key in operations:
                operations[key].append(genome)
            else:
                operations[key] = [genome]
    
    categories = {**validity, **operations}
    return categories


def summarize_genome_issues(genomes) -> None:
    categories = categorize_genome_issues(genomes)
    for key in categories:
        print(f"{len(categories[key])} {key}")


def check_genome_issues(genomes) -> None:
    categories = categorize_genome_issues(genomes)
    for key in categories:
        print(f"{len(categories[key])} {key}:")
        genomes = categories[key]
        for genome in genomes:
            print(genome.short_str())


def report_genome_issues(genomes, report: str) -> None:
    categories = categorize_genome_issues(genomes)
    all_genomes: List[Genome] = categories['valid']

    new_genomes_operations = ("Load from INSDC", "Load from RefSeq", "Load from EnsEMBL")

    new_genomes: List[Genome] = []
    others: List[Genome] = []

    build = 0
    for genome in all_genomes:
        version = str(genome.issue.fixed_version)
        build = int(version[-2:])

        is_new_genome = False
        for op in genome.operations:
            if op in new_genomes_operations:
                is_new_genome = True
        
        if is_new_genome:
            new_genomes.append(genome)
        else:
            others.append(genome)
            others.sort(key=lambda i: i.organism_abbrev)
    
    components = {}
    for genome in new_genomes:
        comp = genome.component
        
        if comp not in components:
            components[comp] = [genome]
        else:
            components[comp].append(genome)
    comp_order = list(components.keys())
    comp_order.sort()

    lines = []
    lines.append("""<html>
<head>
<title>BRC4 genomes report</title>
</head>
<body>
    """)
    lines.append(f"<h1>EBI genomes processing - VEuPathDB build {build}</h1>")
    lines.append(f"<p>{len(all_genomes)} genomes handed over.</p>")
    lines.append(f"<p>{len(new_genomes)} new genomes:</p>")
    lines.append("<ul>")
    for comp in comp_order:
        genomes = components[comp]
        lines.append(f"<li>{len(genomes)} {comp}</li>")
    lines.append("</ul>")

    if others:
        lines.append(f"<p>{len(others)} other operations:</p>")
        lines.append("<ul>")
        for genome in others:
            operations = ", ".join(genome.operations)
            lines.append(f"<li>{operations}: {genome.component} {genome.organism_abbrev} ({genome.redmine_link()})</li>")
        lines.append("</ul>")

    for comp in comp_order:
        comp_issues: List[Genome] = components[comp]
        comp_issues.sort(key=lambda i: i.organism_abbrev)
        lines.append(f"<h2>{comp}</h2>")
        lines.append(f"{len(comp_issues)} new genomes:")
        lines.append("<ul>")
        for genome in comp_issues:
            line_text = f"{genome.organism_abbrev} ({genome.redmine_link()}) {genome.accession}"
            addition = []
            if genome.is_replacement:
                addition.append("replacement")
            if genome.gff:
                addition.append("annotation from separate GFF")
            if addition:
                addition_text = ", ".join(addition)
                line_text += f" ({addition_text})"
            lines.append(f"<li>{line_text}</li>")
        lines.append("</ul>")

    lines.append("""
    <p></p>
    </body>
</html>
    """)
    with open(report, "w") as report_fh:
        report_fh.write("\n".join(lines))


def store_genome_issues(issues, output_dir) -> None:

    group_names = {
        'Reference change': 'reference_change',
        'Load from RefSeq': 'new_genomes',
        'Load from INSDC': 'new_genomes',
        'Allocate stable ids': 'stable_ids',
        'Load from EnsEMBL': 'copy_ensembl',
        'Patch build': 'patch_build',
        'Load from GFF': 'load_gff',
        'Other': 'other',
        'Replacement': 'replacement',
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
                group_name = group.replace(' ', '_')
            group_dir = os.path.join(output_dir, group_name)
            try:
                os.makedirs(group_dir)
            except FileExistsError:
                pass
            
            for genome in genomes:
                if genome.errors:
                    continue
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
    parser.add_argument('--component', type=str,
                        help='Restrict to a given component')
    parser.add_argument('--any_team', action='store_true', dest='any_team',
                        help='Do not filter by the processing team')
    parser.add_argument('--email', type=str,
                        help='Set this email to use Entrez and check the INSDC records')
    args = parser.parse_args()
    
    # Start Redmine API
    redmine = VeupathRedmineClient(key=args.key)
    if args.build:
        redmine.set_build(args.build)
    if args.component:
        redmine.set_component(args.component)

    if args.email:
        Entrez.email = args.email
    issues = get_genome_issues(redmine)

    if args.summary:
        summarize_genome_issues(issues)
    elif args.check:
        check_genome_issues(issues)
    elif args.report:
        report_genome_issues(issues, args.report)
    elif args.store:
        store_genome_issues(issues, args.store)


if __name__ == "__main__":
    main()
