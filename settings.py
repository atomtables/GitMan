# read-only groups
import os

r_groups = ["gitread"]

# allowed groups (can read and write to any repo, but no management)
rw_groups = ["gitwrite"]

# admin groups
admin_groups = ["wheel", "sudo"]

# allowed to create repos only if rw
create_groups = ["gitrepos"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

db_path = os.path.join(BASE_DIR, "users.db")
