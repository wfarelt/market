from apps.users.models import User


def can_view_transfer(user, transfer):
	return user.role in {User.ROLE_SUPERADMIN, User.ROLE_ADMIN} or user.branch_id in {transfer.origin_branch_id, transfer.destination_branch_id}