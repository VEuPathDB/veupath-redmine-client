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
from veupath.redmine.client import VeupathRedmineClient
from veupath.redmine.client.issue_utils import IssueUtils
from veupath.redmine.client.rnaseq import RNAseq

supported_team = "Data Processing (EBI)"
supported_status_id = 20
no_spliced_components = ('TriTrypDB')


def get_rnaseq_issues(redmine: VeupathRedmineClient) -> list:
    """Get issues for all RNA-Seq datasets"""

    datasets = []
    for datatype in RNAseq.supported_datatypes:
        redmine.add_filter("datatype", datatype)
        issues = redmine.get_issues()
        print(f"{len(issues)} issues for datatype '{datatype}'")
        datasets += issues
        redmine.remove_filter("datatype")
    print(f"{len(datasets)} issues for RNA-Seq")
    
    return datasets


def add_no_spliced(issue: RNAseq) -> None:
    if issue.component in no_spliced_components:
        issue.no_spliced = True


def categorize_issues(issues) -> Dict[str, List[RNAseq]]:
    validity: Dict[str, List[RNAseq]] = {
        'valid': [],
        'invalid': [],
    }
    for issue in issues:
        dataset = RNAseq(issue)
        dataset.parse()

        if dataset.errors:
            validity['invalid'].append(dataset)
        else:
            validity['valid'].append(dataset)
    
    categories = validity
    return categories


def check_issues(issues) -> None:
    categories = categorize_issues(issues)
    for key in categories:
        print(f"{len(categories[key])} {key}:")
        genomes = categories[key]
        for genome in genomes:
            print(genome.short_str())


def report_issues(issues, report: str) -> None:
    categories = categorize_issues(issues)
    all_issues: List[RNAseq] = categories['valid']
    if not all_issues:
        print("No valid issue to report")
        return

    build = 0
    components = {}
    for issue in all_issues:
        version = str(issue.issue.fixed_version)
        build = int(version[-2:])
        comp = issue.component
        
        if comp not in components:
            components[comp] = [issue]
        else:
            components[comp].append(issue)
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
    lines.append(f"<p>{len(all_issues)} datasets handed over.</p>")
    lines.append("<ul>")
    for comp in comp_order:
        comp_issues = components[comp]
        lines.append(f"<li>{len(comp_issues)} {comp}</li>")
    lines.append("</ul>")

    lines.append("<h1>New datasets</h1>")
    lines.append("<table>")
    all_issues.sort(key=lambda i: (i.component, i.organism_abbrev, i.dataset_name))
    header = ('Redmine', 'Component', 'Species', 'Dataset', 'Samples')
    lines.append("<tr><th>" + "</th><th>".join(header) + "</th></tr>")
    for issue in all_issues:
        content = (
            issue.redmine_link(),
            issue.component,
            issue.organism_abbrev,
            issue.dataset_name,
            str(len(issue.samples))
        )
        lines.append("<tr><td>" + "</td><td>".join(content) + "</td></tr>")
    lines.append("</table>")

    with open(report, "w") as report_fh:
        report_fh.write("\n".join(lines))


def store_issues(issues, output_dir) -> None:

    categories = categorize_issues(issues)
    all_issues: List[RNAseq] = categories['valid']
    if not all_issues:
        print("No valid issue to report")
        return
    else:
        all_datasets_structs = []
        for dataset in all_issues:
            add_no_spliced(dataset)
            component = dataset.component
            comp_dir = os.path.join(output_dir, component)
            try:
                os.makedirs(comp_dir)
            except FileExistsError:
                pass
        
            dataset_name = f"{dataset.organism_abbrev}_{dataset.dataset_name}"
            organism_file = os.path.join(comp_dir, dataset_name + ".json")
            with open(organism_file, "w") as f:
                dataset_struct = dataset.to_json_struct()
                all_datasets_structs.append(dataset_struct)
                json.dump([dataset_struct], f, indent=True)

        all_structs_file = os.path.join(output_dir, 'all.json')
        with open(all_structs_file, "w") as f:
            json.dump(all_datasets_structs, f, indent=True)


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='List RNA-Seq issues from Redmine')
    
    parser.add_argument('--key', type=str, required=True,
                        help='Redmine authentification key')
    
    parser.add_argument('--list', action='store_true', dest='list',
                        help='Just list all issues')
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
    issues = get_rnaseq_issues(redmine)

    if args.list:
        IssueUtils.print_issues(issues, "RNA-Seq datasets")
    elif args.check:
        check_issues(issues)
    elif args.report:
        report_issues(issues, args.report)
    elif args.store:
        store_issues(issues, args.store)


if __name__ == "__main__":
    main()
