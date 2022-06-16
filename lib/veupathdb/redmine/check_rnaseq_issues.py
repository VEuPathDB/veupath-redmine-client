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
from .client import VeupathRedmineClient
from .issue_utils import IssueUtils
from .rnaseq import RNAseq

supported_team = "Data Processing (EBI)"
supported_status_id = 20


def get_rnaseq_issues(redmine: VeupathRedmineClient) -> list:
    """Get issues for all RNA-Seq datasets"""

    redmine.add_filter("team", supported_team)

    datasets = []
    for datatype in RNAseq.supported_datatypes:
        redmine.add_filter("datatype", datatype)
        issues = redmine.get_issues()
        print(f"{len(issues)} issues for datatype '{datatype}'")
        datasets += issues
        redmine.remove_filter("datatype")
    print(f"{len(datasets)} issues for RNA-Seq")
    
    return datasets


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

    components = {}
    for issue in all_issues:
        comp = issue.component
        
        if comp not in components:
            components[comp] = [issue]
        else:
            components[comp].append(issue)
    comp_order = list(components.keys())
    comp_order.sort()

    lines = []
    lines.append(f"{len(all_issues)} datasets handed over:")
    for comp in comp_order:
        issues = components[comp]
        lines.append(f"\t- {len(issues)} {comp}")

    lines.append("New datasets")
    all_issues.sort(key=lambda i: (i.component, i.organism_abbrev, i.dataset_name))
    lines.append("Component\tSpecies\tDataset\tSamples")
    for issue in all_issues:
        lines.append(f"{issue.component}\t{issue.organism_abbrev}\t{issue.dataset_name}\t{len(issue.samples)}")

    with open(report, "w") as report_fh:
        report_fh.write("\n".join(lines))


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
    # Optional
    parser.add_argument('--build', type=int,
                        help='Restrict to a given build')
    args = parser.parse_args()
    
    # Start Redmine API
    redmine = VeupathRedmineClient(key=args.key)
    if args.build:
        redmine.set_build(args.build)

    issues = get_rnaseq_issues(redmine)

    if args.list:
        IssueUtils.print_issues(issues, "RNA-Seq datasets")
    elif args.check:
        check_issues(issues)
    elif args.report:
        report_issues(issues, args.report)


if __name__ == "__main__":
    main()
