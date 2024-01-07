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

def user_in_group(user: str, group: list) -> bool:
    for group in group:
        if is_user_in_group(user, group):
            return True
    return False

def create_new_user(username: str, role: str, create_repos: bool, use_ssh: bool):
    """
    Commands required for creating a new user:
    - *sudo* useradd username;
    - *sudo* passwd username --expire; so they can set their own password on first login
    - depending on role: *sudo* usermod -aG *role* username
    - depending on if they are allowed to create repos: *sudo* usermod -aG gitrepos username
    - if user is allowed ssh access: *sudo* usermod -aG ssh-users username
    :return:
    """
    try:
        subprocess.run(['sudo', 'useradd', username], check=True)
    except subprocess.CalledProcessError as e:
        print(e)
        return False

    try:
        subprocess.run(['sudo', 'passwd', username, '--expire'], check=True)
    except subprocess.CalledProcessError as e:
        print(e)
        try:
            subprocess.run(['sudo', 'userdel', username], check=True)
        except subprocess.CalledProcessError as e:
            print(e)
            return False
        return False

    if role == "Read-Only":
        try:
            subprocess.run(['sudo', 'usermod', '-aG', 'gitread', username], check=True)
        except subprocess.CalledProcessError as e:
            print(e)
            try:
                subprocess.run(['sudo', 'userdel', username], check=True)
            except subprocess.CalledProcessError as e:
                print(e)
                return False
            return False
    elif role == "Read-Write":
        try:
            subprocess.run(['sudo', 'usermod', '-aG', 'gitwrite', username], check=True)
        except subprocess.CalledProcessError as e:
            print(e)
            try:
                subprocess.run(['sudo', 'userdel', username], check=True)
            except subprocess.CalledProcessError as e:
                print(e)
                return False
            return False
    elif role == "Admin":
        try:
            subprocess.run(['sudo', 'usermod', '-aG', 'sudo', username], check=True)
        except subprocess.CalledProcessError as e:
            print(e)
            try:
                subprocess.run(['sudo', 'userdel', username], check=True)
            except subprocess.CalledProcessError as e:
                print(e)
                return False
            return False

    if create_repos:
        try:
            subprocess.run(['sudo', 'usermod', '-aG', 'gitrepos', username], check=True)
        except subprocess.CalledProcessError as e:
            print(e)
            try:
                subprocess.run(['sudo', 'userdel', username], check=True)
            except subprocess.CalledProcessError as e:
                print(e)
                return False
            return False

    if use_ssh:
        try:
            subprocess.run(['sudo', 'usermod', '-aG', 'ssh-users', username], check=True)
        except subprocess.CalledProcessError as e:
            print(e)
            try:
                subprocess.run(['sudo', 'userdel', username], check=True)
            except subprocess.CalledProcessError as e:
                print(e)
                return False
            return False

    return True