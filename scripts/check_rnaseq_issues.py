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
from pathlib import Path
from typing import Dict, List

from veupath.redmine.client import VeupathRedmineClient
from veupath.redmine.client.rnaseq import RNAseq
from veupath.redmine.client.orgs_utils import OrgsUtils

supported_team = "Data Processing (EBI)"
supported_status_id = 20
no_spliced_components = ('TriTrypDB', 'MicrospordiaDB')

valid_status_handover = ('New', 'Data Processing (EBI)')
valid_status_anytime = (
    'New',
    'Data Processing (EBI)',
    'Ready for Release',
    'Post Loading Config and QA',
    'Pre-loading data preparation',
    'Assessment for Loading',
    'Outreach QA',
    )

def get_rnaseq_issues(redmine: VeupathRedmineClient) -> List[RNAseq]:
    """Get issues for all RNA-Seq datasets"""

    datasets = []
    for datatype in RNAseq.supported_datatypes:
        redmine.add_filter("datatype", datatype)
        issues = redmine.get_issues()
        print(f"{len(issues)} issues for datatype '{datatype}'")
        for issue in issues:
            dataset = RNAseq(issue)
            dataset.parse()
            datasets.append(dataset)
        redmine.remove_filter("datatype")
    print(f"{len(datasets)} issues for RNA-Seq")
    
    return datasets


def add_no_spliced(dataset: RNAseq) -> None:
    if dataset.component in no_spliced_components:
        dataset.no_spliced = True


def categorize_datasets(datasets: List[RNAseq]) -> Dict[str, List[RNAseq]]:
    validity: Dict[str, List[RNAseq]] = {
        'valid': [],
        'invalid': [],
        'reference_change': [],
        'patch_build': [],
        'new': [],
        'new_genome': [],
        'other': [],
    }
    for dataset in datasets:

        if dataset.errors:
            validity['invalid'].append(dataset)
        else:
            if dataset.is_ref_change:
                validity['reference_change'].append(dataset)
            elif "Patch build" in dataset.operations:
                validity['patch_build'].append(dataset)
            elif "Other" in dataset.operations:
                validity['other'].append(dataset)
            elif dataset.new_genome:
                validity['new_genome'].append(dataset)
            else:
                validity['new'].append(dataset)
            validity['valid'].append(dataset)
    
    categories = validity
    return categories


def check_datasets(datasets) -> None:
    categories = categorize_datasets(datasets)
    for key in categories:
        print(f"\n{len(categories[key])} {key}:")
        genomes = categories[key]
        for genome in genomes:
            print(genome.short_str())


def report_issues(datasets: List[RNAseq], report: str) -> None:
    categories = categorize_datasets(datasets)
    all_datasets: List[RNAseq] = categories['valid']
    if not all_datasets:
        print("No valid dataset to report")
        return

    new: List[RNAseq] = categories['new']
    new_genome: List[RNAseq] = categories['new_genome']
    new += new_genome
    remaps: List[RNAseq] = categories['reference_change']
    others: List[RNAseq] = categories['other']

    build = 0
    components = {}
    for dataset in new:
        version = str(dataset.issue.fixed_version)
        build = int(version[-2:])
        comp = dataset.component
        
        if comp not in components:
            components[comp] = [dataset]
        else:
            components[comp].append(dataset)
    comp_order = list(components.keys())
    comp_order.sort()

    lines = []

    lines.append("""<html>
<head>
<title>BRC4 RNA-Seq report</title>
<style>
table {
  border-collapse: collapse;
}

td,
th {
  border-width: 1px;
  border-color: black;
  border-style: solid;
  font-size: small;
}
</style>
</head>
<body>
    """)
    lines.append(f"<h1>EBI RNA-Seq processing - VEuPathDB build {build}</h1>")
    lines.append(f"<p>{len(new)} new datasets handed over:</p>")
    lines.append("<ul>")
    for comp in comp_order:
        comp_issues = components[comp]
        lines.append(f"<li>{len(comp_issues)} {comp}</li>")
    lines.append("</ul>")

    if remaps:
        lines.append(f"<p>{len(remaps)} genomes remapped:</p>")
        lines.append("<ul>")
        for dataset in remaps:
            line_text = f"{dataset.component} {dataset.organism_abbrev} ({dataset.redmine_link()})"
            lines.append(f"<li>{line_text}</li>")
        lines.append("</ul>")

    if others:
        lines.append(f"<p>{len(others)} other operations:</p>")
        lines.append("<ul>")
        for other in others:
            operations = ", ".join(other.operations)
            line_text = f"{operations}: {other.component} {other.organism_abbrev} ({other.redmine_link()})"
            lines.append(f"<li>{line_text}</li>")
        lines.append("</ul>")

    lines.append("<h1>New datasets</h1>")
    lines.append("<table>")
    new.sort(key=lambda i: (i.component, i.organism_abbrev, i.dataset_name))
    header = ('Redmine', 'Component', 'Species', 'Dataset', 'Samples', 'Notes')
    lines.append("<tr><th>" + "</th><th>".join(header) + "</th></tr>")
    for dataset in new:
        content = (
            dataset.redmine_link(),
            dataset.component,
            dataset.organism_abbrev,
            dataset.dataset_name,
            str(len(dataset.samples)),
            ""
        )
        lines.append("<tr><td>" + "</td><td>".join(content) + "</td></tr>")
    lines.append("</table>")

    with open(report, "w") as report_fh:
        report_fh.write("\n".join(lines))


def store_issues(issues, output_dir: Path) -> None:

    categories = categorize_datasets(issues)
    all_datasets: List[RNAseq] = categories['valid']
    if not all_datasets:
        print("No valid dataset to report")
        return
    else:
        cur_datasets_structs = []
        new_datasets_structs = []
        for dataset in all_datasets:
            sub_dir = "cur_genome"
            if dataset.is_ref_change:
                continue
            elif "Other" in dataset.operations:
                sub_dir = "other"
            elif "Patch build" in dataset.operations:
                sub_dir = "patch_build"
            elif dataset.new_genome:
                print(f"Dataset is for new genome {dataset.issue.id}")
                sub_dir = "new_genome"

            add_no_spliced(dataset)
            component = dataset.component
            comp_dir = Path(output_dir) / sub_dir / component
            try:
                comp_dir.mkdir(parents=True)
            except FileExistsError:
                pass
        
            dataset_name = f"{dataset.organism_abbrev}_{dataset.dataset_name}"
            organism_file = comp_dir / f"{dataset_name}.json"
            with organism_file.open("w") as f:
                dataset_struct = dataset.to_json_struct()
                if dataset.new_genome:
                    new_datasets_structs.append(dataset_struct)
                elif "Other" not in dataset.operations and "Patch build" not in dataset.operations:
                    cur_datasets_structs.append(dataset_struct)
                json.dump([dataset_struct], f, indent=True, sort_keys=True)

        cur_structs_file = output_dir / 'all_cur.json'
        with cur_structs_file.open("w") as f:
            json.dump(cur_datasets_structs, f, indent=True, sort_keys=True)

        if new_datasets_structs:
            new_structs_file = output_dir / 'all_new.json'
            with new_structs_file.open("w") as f:
                json.dump(new_datasets_structs, f, indent=True, sort_keys=True)


def filter_valid_status(datasets: List[RNAseq], valid_status) -> List:
    valid_datasets = []
    for dataset in datasets:
        if str(dataset.issue.status) in valid_status:
            valid_datasets.append(dataset)
        else:
            print(f"Excluded: {dataset} = {dataset.issue.id} - {dataset.issue.status}")
    return valid_datasets


def add_abbrev_flag(datasets: List[RNAseq], abbrev_file: Path) -> List:
    cur_abbrevs = OrgsUtils.load_abbrevs(abbrev_file)

    for dataset in datasets:
        if dataset.organism_abbrev.lower() not in cur_abbrevs:
            dataset.new_genome = True

    return datasets


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='List RNA-Seq issues from Redmine')
    
    parser.add_argument('--key', type=str, required=True,
                        help='Redmine authentification key')
    
    parser.add_argument('--check', action='store_true', dest='check',
                        help='Parse issues and report errors')
    parser.add_argument('--report', type=str,
                        help='Write a report to a file')
    parser.add_argument('--store', type=str,
                        help='Write json files for each Redmine issue')
    # Optional
    parser.add_argument('--build', type=int,
                        help='Restrict to a given build')
    parser.add_argument('--component', type=str,
                        help='Restrict to a given component')
    parser.add_argument('--species', type=str,
                        help='Get all RNA-Seq data for a given species (organism_abbrev)')
    parser.add_argument('--any_team', action='store_true', dest='any_team',
                        help='Do not filter by the processing team')
    parser.add_argument('--valid_status', action='store_true', dest='valid_status',
                        help='Filter out invalid status')
    parser.add_argument('--current_abbbrevs', type=str, dest='current_abbrevs',
                        help='A file that contains current abbrevs (otherwise dataset is for a new genome)')
    args = parser.parse_args()
    
    # Start Redmine API
    redmine = VeupathRedmineClient(key=args.key)

    if not args.any_team:
        redmine.add_filter("team", supported_team)
    if args.build:
        redmine.set_build(args.build)
    if args.component:
        redmine.set_component(args.component)

    if args.species:
        redmine.set_organism(args.species)
    datasets = get_rnaseq_issues(redmine)
    
    if args.current_abbrevs:
        datasets = add_abbrev_flag(datasets, Path(args.current_abbrevs))
    
    for dat in datasets:
        if dat.new_genome:
            print(f"New genome for {dat}")

    if args.valid_status:
        datasets = filter_valid_status(datasets, valid_status_anytime)
        print(f"After valid status filter (anytime valid): {len(datasets)}")
    else:
        datasets = filter_valid_status(datasets, valid_status_handover)
        print(f"After valid status filter (handover valid): {len(datasets)}")

    if args.check:
        check_datasets(datasets)
    elif args.report:
        report_issues(datasets, args.report)
    elif args.store:
        store_issues(datasets, Path(args.store))


if __name__ == "__main__":
    main()
