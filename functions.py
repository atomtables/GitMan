import datetime
import subprocess
import os
import git
from git import Repo


def is_git_repo(path):
    try:
        _ = git.Repo(path).git_dir
        return True
    except git.exc.InvalidGitRepositoryError:
        return False


def get_last_commit_time(repo_path):
    try:
        repo = Repo(repo_path)
        last_commit = next(repo.iter_commits())
        return last_commit.committed_datetime
    except Exception:
        # TypeError: can't compare offset-naive and offset-aware datetimes
        return datetime.datetime(1970, 1, 1, 0, 0, 0, 0, datetime.timezone.utc)


def count_commits(repo_path):
    try:
        # Change to the repository directory
        os.chdir(repo_path)

        # Run the git command to count commits
        result = subprocess.check_output(['git', 'rev-list', '--all', '--count']).decode('utf-8').strip()

        return int(result)
    except subprocess.CalledProcessError as e:
        print(f"Error counting commits in {repo_path}: {e}")
        return 0


def is_user_in_group(username, group):
    try:
        result = subprocess.run(['id', '-nG', username], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                check=True)
        groups = result.stdout.strip().split()
        return group in groups
    except subprocess.CalledProcessError:
        return False

def is_password_change_required(username):
    try:
        result = subprocess.run(['chage', '-l', username], capture_output=True, text=True, check=True)
        return 'password must be changed' in result.stdout
    except subprocess.CalledProcessError:
        return None

