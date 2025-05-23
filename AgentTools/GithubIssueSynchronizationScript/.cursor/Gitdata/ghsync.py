#!/usr/bin/env python3
import subprocess
import json
import os
import sys
import argparse
import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SUMMARY_FILE = os.path.join(SCRIPT_DIR, "gitsync_open_issues_summary.json")
LAST_RUN_FILE = os.path.join(SCRIPT_DIR, "gitsync_last_run.json")


def write_status_file(operation, operation_status, operation_message, issue_number=None, error_details=None):
    """Writes status info to LAST_RUN_FILE."""
    payload = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "operation": operation,
        "operation_status": operation_status,
        "issue_number": int(issue_number) if issue_number else None,
        "operation_message": operation_message,
        "script_error_details": error_details,
    }
    try:
        with open(LAST_RUN_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Failed to write status file: {e}", file=sys.stderr)


def run_gh_command(cmd):
    """Runs a gh command and returns CompletedProcess."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result
    except FileNotFoundError:
        print("gh CLI not found. Please install GitHub CLI and authenticate via 'gh auth login'.", file=sys.stderr)
        sys.exit(1)


def load_existing_cache():
    """Load existing cache if it exists, return empty structure otherwise."""
    try:
        with open(SUMMARY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"labels": [], "issues": []}


def get_issue_last_updated_list(owner, repo):
    """Get a list of all issues with their numbers and updatedAt timestamps."""
    # ! Fetch all issues with minimal data to check update times
    cmd = ["gh", "issue", "list", "--repo", f"{owner}/{repo}", "--state", "all", 
           "--limit", "1000", "--json", "number,updatedAt,state,stateReason"]
    res = run_gh_command(cmd)
    if res.returncode != 0:
        return []
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        return []


def fetch_issue_details(owner, repo, issue_number):
    """Fetch detailed information for a specific issue including comments."""
    # * Get detailed issue data
    view_cmd = ["gh", "issue", "view", str(issue_number), "--repo", f"{owner}/{repo}", 
                "--json", "number,title,body,labels,comments,state,stateReason"]
    view_res = run_gh_command(view_cmd)
    if view_res.returncode == 0:
        try:
            return json.loads(view_res.stdout)
        except json.JSONDecodeError:
            return None
    return None


def download(owner, repo):
    """Fetch labels and all issues with smart caching based on updatedAt."""
    # Fetch labels (these change rarely, so we can fetch them each time)
    label_cmd = ["gh", "label", "list", "--repo", f"{owner}/{repo}", "--json", "name,description,color"]
    lbl_res = run_gh_command(label_cmd)
    if lbl_res.returncode != 0:
        write_status_file("Download", "failure", lbl_res.stderr)
        print(lbl_res.stderr, file=sys.stderr)
        sys.exit(1)
    labels = json.loads(lbl_res.stdout)

    # Load existing cache
    cache = load_existing_cache()
    cached_issues = {issue["number"]: issue for issue in cache.get("issues", [])}
    
    # Get list of all issues with update times and state information
    all_issues_update_info = get_issue_last_updated_list(owner, repo)
    
    updated_issues = []
    new_issues_count = 0
    updated_issues_count = 0
    
    for issue_info in all_issues_update_info:
        issue_num = issue_info["number"]
        updated_at = issue_info["updatedAt"]
        
        # Check if we need to update this issue
        cached_issue = cached_issues.get(issue_num)
        needs_update = True
        
        if cached_issue:
            # Compare updatedAt timestamps
            cached_updated_at = cached_issue.get("updatedAt")
            if cached_updated_at == updated_at:
                needs_update = False
                updated_issues.append(cached_issue)
            else:
                updated_issues_count += 1
        else:
            new_issues_count += 1
            
        if needs_update:
            # Fetch detailed issue data
            detailed_issue = fetch_issue_details(owner, repo, issue_num)
            if detailed_issue:
                # Add updatedAt timestamp for future comparisons
                detailed_issue["updatedAt"] = updated_at
                updated_issues.append(detailed_issue)
    
    # * Sort issues by state: open, closed (completed), closed (not planned)
    def get_sort_key(issue):
        state = issue.get("state", "OPEN").upper()
        state_reason = issue.get("stateReason", "").upper()
        
        if state == "OPEN":
            return (0, issue["number"])  # Open issues first
        elif state == "CLOSED":
            if state_reason == "NOT_PLANNED":
                return (2, issue["number"])  # Not planned issues last
            else:
                return (1, issue["number"])  # Completed issues second
        else:
            return (3, issue["number"])  # Unknown states at the end
    
    updated_issues.sort(key=get_sort_key)

    # Write updated summary
    try:
        with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
            f.write("{\n")
            # Labels array on a single line
            f.write(f'  "labels": {json.dumps(labels, ensure_ascii=False, separators=(',', ':'))},\n')
            f.write('  "issues": [\n')
            # Each issue object on its own line
            for i, issue in enumerate(updated_issues):
                f.write(f'    {json.dumps(issue, ensure_ascii=False, separators=(',', ':'))}')
                if i < len(updated_issues) - 1:
                    f.write(",")
                f.write("\n")
            f.write("  ]\n")
            f.write("}\n")
        
        # * Count issues by state for reporting
        open_count = sum(1 for issue in updated_issues if issue.get("state", "").upper() == "OPEN")
        closed_completed_count = sum(1 for issue in updated_issues 
                                   if issue.get("state", "").upper() == "CLOSED" 
                                   and issue.get("stateReason", "").upper() != "NOT_PLANNED")
        closed_not_planned_count = sum(1 for issue in updated_issues 
                                     if issue.get("state", "").upper() == "CLOSED" 
                                     and issue.get("stateReason", "").upper() == "NOT_PLANNED")
        
        msg = f"Download: fetched {len(labels)} labels and {len(updated_issues)} issues ({open_count} open, {closed_completed_count} closed, {closed_not_planned_count} not planned). {new_issues_count} new, {updated_issues_count} updated."
        write_status_file("Download", "success", msg)
        print(msg)
    except Exception as e:
        write_status_file("Download", "failure", str(e))
        print(f"Failed to write summary file: {e}", file=sys.stderr)
        sys.exit(1)


def upload(owner, repo, title, body, labels, body_from_file=None):
    """Create a new issue with given title, body, and labels."""
    # * Read body from file if specified
    if body_from_file:
        try:
            # * Construct the full path assuming body files are in temp_bodies
            full_body_file_path = os.path.join(SCRIPT_DIR, "temp_bodies", body_from_file)
            with open(full_body_file_path, 'r', encoding='utf-8') as f:
                body = f.read().strip()
            # * Delete the file after reading
            os.remove(full_body_file_path)
            print(f"Deleted temporary body file: {full_body_file_path}")
        except FileNotFoundError:
            err = f"Body file not found: {body_from_file} in temp_bodies"
            write_status_file("Upload", "failure", err)
            print(err, file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            err = f"Error reading body file: {e}"
            write_status_file("Upload", "failure", err)
            print(err, file=sys.stderr)
            sys.exit(1)
    
    # * Fix line breaks in body - convert \n to actual newlines
    if body:
        body = body.replace('\\n', '\n').replace('\\t', '\t')
    
    # Get valid repo labels to filter
    label_cmd = ["gh", "label", "list", "--repo", f"{owner}/{repo}", "--json", "name"]
    lbl_res = run_gh_command(label_cmd)
    valid_labels = []
    if lbl_res.returncode == 0:
        valid_labels = [l.get("name") for l in json.loads(lbl_res.stdout)]
    # Filter provided labels
    labels_to_use = [l for l in labels if l in valid_labels]
    if labels and not labels_to_use:
        err = f"No valid labels provided. Repo labels: {valid_labels}"  
        write_status_file("Upload", "failure", err)
        print(err, file=sys.stderr)
        sys.exit(1)

    # Build create command
    cmd = ["gh", "issue", "create", "--repo", f"{owner}/{repo}", "--title", title]
    if body: cmd += ["--body", body]
    for l in labels_to_use:
        cmd += ["--label", l]
    cmd += ["--json", "number"]

    res = run_gh_command(cmd)
    if res.returncode == 0:
        # gh --json supported
        data = json.loads(res.stdout)
        num = data.get("number")
        msg = f"Upload: Successfully created issue #{num}."
        write_status_file("Upload", "success", msg, issue_number=num)
        print(msg)
        return
    # Handle gh versions without --json support
    stderr = res.stderr or ""
    if "unknown flag: --json" in stderr:
        # Retry without --json and parse URL
        fallback_cmd = cmd[:-2]
        fb_res = run_gh_command(fallback_cmd)
        if fb_res.returncode == 0:
            url = fb_res.stdout.strip()
            import re
            m = re.search(r'/issues/(\d+)', url)
            num = m.group(1) if m else None
            if num:
                msg = f"Upload: Successfully created issue #{num} (parsed from URL)."
                write_status_file("Upload", "success", msg, issue_number=num)
                print(msg)
                return
    # Fallback: check last run file
    try:
        lr = json.load(open(LAST_RUN_FILE, "r", encoding="utf-8"))
        if lr.get("operation") == "Upload" and lr.get("operation_status") == "success":
            num = lr.get("issue_number")
            msg = f"Upload fallback: confirmed issue #{num} via last_run status."
            print(msg)
            write_status_file("Upload", "success", msg, issue_number=num)
            sys.exit(0)
    except Exception:
        pass
    # Final failure
    write_status_file("Upload", "failure", stderr)
    print(stderr, file=sys.stderr)
    sys.exit(1)


def edit(owner, repo, issue_number, new_title=None, new_body=None, new_labels=None, new_state=None, body_from_file=None):
    """Edit an existing issue with new title, body, labels, or state."""
    # * Read body from file if specified
    if body_from_file:
        try:
            # * Construct the full path assuming body files are in temp_bodies
            full_body_file_path = os.path.join(SCRIPT_DIR, "temp_bodies", body_from_file)
            with open(full_body_file_path, 'r', encoding='utf-8') as f:
                new_body = f.read().strip()
            # * Delete the file after reading
            os.remove(full_body_file_path)
            print(f"Deleted temporary body file: {full_body_file_path}")
        except FileNotFoundError:
            err = f"Body file not found: {body_from_file} in temp_bodies"
            write_status_file("Edit", "failure", err, issue_number=issue_number)
            print(err, file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            err = f"Error reading body file: {e}"
            write_status_file("Edit", "failure", err, issue_number=issue_number)
            print(err, file=sys.stderr)
            sys.exit(1)
    
    # * Fix line breaks in body - convert \n to actual newlines
    if new_body:
        new_body = new_body.replace('\\n', '\n').replace('\\t', '\t')
    
    # Get valid repo labels to filter
    valid_labels = []
    if new_labels:
        label_cmd = ["gh", "label", "list", "--repo", f"{owner}/{repo}", "--json", "name"]
        lbl_res = run_gh_command(label_cmd)
        if lbl_res.returncode == 0:
            valid_labels = [l.get("name") for l in json.loads(lbl_res.stdout)]
        # Filter provided labels
        labels_to_use = [l for l in new_labels if l in valid_labels]
        if new_labels and not labels_to_use:
            err = f"No valid labels provided. Repo labels: {valid_labels}"  
            write_status_file("Edit", "failure", err, issue_number=issue_number)
            print(err, file=sys.stderr)
            sys.exit(1)
        new_labels = labels_to_use

    # * Handle state changes using separate commands
    if new_state:
        state_lower = new_state.lower()
        if state_lower == "open":
            # Reopen the issue
            reopen_cmd = ["gh", "issue", "reopen", str(issue_number), "--repo", f"{owner}/{repo}"]
            reopen_res = run_gh_command(reopen_cmd)
            if reopen_res.returncode != 0:
                stderr = reopen_res.stderr or reopen_res.stdout or "Unknown error"
                write_status_file("Edit", "failure", f"Failed to reopen issue: {stderr}", issue_number=issue_number)
                print(f"Failed to reopen issue #{issue_number}: {stderr}", file=sys.stderr)
                sys.exit(1)
        elif state_lower == "closed":
            # Close the issue as completed
            close_cmd = ["gh", "issue", "close", str(issue_number), "--repo", f"{owner}/{repo}", "--reason", "completed"]
            close_res = run_gh_command(close_cmd)
            if close_res.returncode != 0:
                stderr = close_res.stderr or close_res.stdout or "Unknown error"
                write_status_file("Edit", "failure", f"Failed to close issue: {stderr}", issue_number=issue_number)
                print(f"Failed to close issue #{issue_number}: {stderr}", file=sys.stderr)
                sys.exit(1)
        elif state_lower == "not_planned" or state_lower == "not planned":
            # Close the issue as not planned
            close_cmd = ["gh", "issue", "close", str(issue_number), "--repo", f"{owner}/{repo}", "--reason", "not planned"]
            close_res = run_gh_command(close_cmd)
            if close_res.returncode != 0:
                stderr = close_res.stderr or close_res.stdout or "Unknown error"
                write_status_file("Edit", "failure", f"Failed to close issue as not planned: {stderr}", issue_number=issue_number)
                print(f"Failed to close issue #{issue_number} as not planned: {stderr}", file=sys.stderr)
                sys.exit(1)
        else:
            err = f"Invalid state '{new_state}'. Valid states: open, closed, not_planned"
            write_status_file("Edit", "failure", err, issue_number=issue_number)
            print(err, file=sys.stderr)
            sys.exit(1)

    # * Handle other edits (title, body, labels) if any are specified
    if new_title or new_body or new_labels:
        # Build edit command
        cmd = ["gh", "issue", "edit", str(issue_number), "--repo", f"{owner}/{repo}"]
        
        if new_title:
            cmd += ["--title", new_title]
        if new_body:
            cmd += ["--body", new_body]
        if new_labels:
            # ! Simply add new labels without removing existing ones
            for label in new_labels:
                cmd += ["--add-label", label]

        res = run_gh_command(cmd)
        if res.returncode != 0:
            stderr = res.stderr or res.stdout or "Unknown error"
            write_status_file("Edit", "failure", stderr, issue_number=issue_number)
            print(f"Failed to edit issue #{issue_number}: {stderr}", file=sys.stderr)
            sys.exit(1)

    msg = f"Edit: Successfully updated issue #{issue_number}."
    write_status_file("Edit", "success", msg, issue_number=issue_number)
    print(msg)


def main():
    parser = argparse.ArgumentParser(description="ghsync: sync GitHub issues via gh CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-d", "--download", action="store_true", help="Fetch labels and all issues")
    group.add_argument("-u", "--upload", action="store_true", help="Create a new issue")
    group.add_argument("-e", "--edit", type=int, metavar="ISSUE_NUMBER", help="Edit an existing issue")
    parser.add_argument("--owner", default="Artemonim", help="Repo owner")
    parser.add_argument("--repo", default="Artemonim-s-Task-Manager", help="Repo name")
    parser.add_argument("--title", help="Issue title for upload mode")
    parser.add_argument("--body", help="Issue body for upload mode")
    parser.add_argument("--body-from-file", help="Read issue body from file in temp_bodies for upload mode")
    parser.add_argument("--labels", nargs="*", default=[], help="Issue labels for upload mode")
    
    # Edit mode arguments
    parser.add_argument("-NewTitle", help="New title for edit mode")
    parser.add_argument("-NewBody", help="New body for edit mode")
    parser.add_argument("-NewBodyFromFile", help="Read new body from file in temp_bodies for edit mode")
    parser.add_argument("-NewLabels", nargs="*", help="New labels for edit mode")
    parser.add_argument("-NewState", choices=["open", "closed", "not_planned", "not planned"], help="New state for edit mode: open, closed, not_planned")
    
    args = parser.parse_args()

    if args.download:
        download(args.owner, args.repo)
    elif args.upload:
        if not args.title:
            parser.error("--title is required for upload mode")
        upload(args.owner, args.repo, args.title, args.body, args.labels, args.body_from_file)
    elif args.edit:
        if not any([args.NewTitle, args.NewBody, args.NewBodyFromFile, args.NewLabels, args.NewState]):
            parser.error("At least one of -NewTitle, -NewBody, -NewBodyFromFile, -NewLabels, or -NewState is required for edit mode")
        edit(args.owner, args.repo, args.edit, args.NewTitle, args.NewBody, args.NewLabels, args.NewState, args.NewBodyFromFile)

if __name__ == "__main__":
    main()
