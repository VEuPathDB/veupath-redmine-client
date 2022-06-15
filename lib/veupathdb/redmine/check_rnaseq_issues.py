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
from .client import IssueUtils, VeupathRedmineClient

supported_datatypes = (
    "RNA-seq",
    #"DNA-seq",
)
supported_team = "Data Processing (EBI)"
supported_status_id = 20


def get_rnaseq_issues(redmine: VeupathRedmineClient) -> list:
    """Get issues for all RNA-Seq datasets"""

    redmine.add_filter("team", supported_team)

    datasets = []
    for datatype in supported_datatypes:
        redmine.add_filter("datatype", datatype)
        issues = redmine.get_issues()
        print(f"{len(issues)} issues for datatype '{datatype}'")
        datasets += issues
        redmine.remove_filter("datatype")
    print(f"{len(datasets)} issues for RNA-Seq")
    
    return datasets


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='List RNA-Seq issues from Redmine')
    
    parser.add_argument('--key', type=str, required=True,
                        help='Redmine authentification key')
    # Choice
    parser.add_argument('--action',
                        choices=[
                            'list',
                            'check',
                            'count',
                        ],
                        required=True,
                        help='What to do with the list of RNA-Seq issues')
    # Optional
    parser.add_argument('--build', type=int,
                        help='Restrict to a given build')
    args = parser.parse_args()
    
    # Start Redmine API
    redmine = VeupathRedmineClient(key=args.key)
    if args.build:
        redmine.set_build(args.build)

    issues = get_rnaseq_issues(redmine)

    if args.action == "count":
        pass
    if args.action == "list":
        IssueUtils.print_issues(issues, "RNA-Seq datasets")
    elif args.action == "check":
        # TODO
        pass


if __name__ == "__main__":
    main()
