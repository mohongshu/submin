from submin.dispatch.view import View
from submin.template.shortcuts import evaluate_main
from submin.dispatch.response import Response, XMLStatusResponse, XMLTemplateResponse
from submin.views.error import ErrorResponse
from submin.models.user import User
from submin.models.exceptions import UnknownUserError, UserExistsError, \
		UserPermissionError, MemberExistsError
from submin.models.group import Group
from submin.auth.decorators import *
from submin.models.options import Options
from submin.models import validators
from submin.unicode import uc_str

class Users(View):
	@login_required
	def handler(self, req, path):
		localvars = {}
		o = Options()

		if req.is_ajax():
			return self.ajaxhandler(req, path)

		if len(path) < 1:
			return ErrorResponse('Invalid path', request=req)

		if len(path) > 0:
			localvars['selected_type'] = 'users'
		if len(path) > 1:
			localvars['selected_object'] = path[1]

		try:
			if path[0] == 'show':
				return self.show(req, path[1:], localvars)
			if path[0] == 'add':
				return self.add(req, path[1:], localvars)
		except Unauthorized:
			return Redirect(o.value('base_url_submin'))

		return ErrorResponse('Unknown path', request=req)

	def show(self, req, path, localvars):
		if len(path) < 1:
			return ErrorResponse('Invalid path', request=req)

		is_admin = req.session['user'].is_admin
		if not is_admin and path[0] != req.session['user'].name:
			raise Unauthorized('Permission denied to view this user')

		try:
			user = User(path[0])
		except (IndexError, UnknownUserError):
			return ErrorResponse('This user does not exist.', request=req)

		localvars['user'] = user
		formatted = evaluate_main('users.html', localvars, request=req)
		return Response(formatted)

	def showAddForm(self, req, username, email, fullname, errormsg=''):
		localvars = {}
		localvars['errormsg'] = errormsg
		localvars['username'] = username
		localvars['email'] = email
		localvars['fullname'] = fullname
		formatted = evaluate_main('newuser.html', localvars, request=req)
		return Response(formatted)

	@admin_required
	def add(self, req, path, localvars):
		o = Options()
		base_url = o.url_path('base_url_submin')
		username = ''
		email = ''
		fullname = ''

		if req.post and req.post['username'] and req.post['email'] and req.post['fullname']:
			import re

			username = uc_str(req.post['username'].value.strip())
			email = uc_str(req.post['email'].value.strip())
			fullname = uc_str(req.post['fullname'].value.strip())

			# check these before we add the user, the rest is checked when adding
			try:
				validators.validate_email(email)
				validators.validate_fullname(fullname)
			except validators.InvalidEmail:
				return self.showAddForm(req, username, email, fullname,
					'Email is not valid')
			except validators.InvalidFullname:
				return self.showAddForm(req, username, email, fullname,
					'Invalid characters in full name')

			if username == '':
				return self.showAddForm(req, username, email, fullname,
					'Username not supplied')

			if email == '':
				return self.showAddForm(req, username, email, fullname,
					'Email must be supplied')

			try:
				u = User.add(username)
				u.email = email
				u.fullname = fullname
			except IOError:
				return ErrorResponse('File permission denied', request=req)
			except UserExistsError:
				return self.showAddForm(req, username, email, fullname,
					'User %s already exists' % username)
			except validators.InvalidUsername:
				return self.showAddForm(req, username, email, fullname,
					'Invalid characters in username')

			url = base_url + '/users/show/' + username
			return Redirect(url)

		return self.showAddForm(req, username, email, fullname)

	def ajaxhandler(self, req, path):
		username = ''

		if len(path) < 2:
			return XMLStatusResponse('', False, 'Invalid path')

		action = path[0]
		username = path[1]

		if action == 'delete':
			return self.removeUser(req, username)

		user = User(username)
		
		if 'fullname' in req.post and req.post['fullname'].value.strip():
			return self.setFullName(req, user)
		
		if 'email' in req.post and req.post['email'].value.strip():
			return self.setEmail(req, user)

		if 'password' in req.post and req.post['password'].value.strip():
			return self.setPassword(req, user)

		if 'addToGroup' in req.post:
			return self.addToGroup(req, user)

		if 'removeFromGroup' in req.post:
			return self.removeFromGroup(req, user)

		if 'listUserGroups' in req.post:
			return self.listUserGroups(req, user)

		if 'listNotifications' in req.post:
			return self.listNotifications(req, user)
		
		if 'saveNotifications' in req.post:
			return self.saveNotifications(req, user)
		
		if 'setIsAdmin' in req.post:
			return self.setIsAdmin(req, user)

		return XMLStatusResponse('', False, 'Unknown command')

	def setEmail(self, req, user):
		try:
			user.email = uc_str(req.post.get('email'))
			return XMLStatusResponse('email', True,
				'Changed email address for user %s to %s' %
				(user.name, user.email))
		except validators.InvalidEmail:
			return XMLStatusResponse('email', False,
				'Invalid characters in email-address. If you think this is an error, please report a bug')
		except Exception, e:
			return XMLStatusResponse('email', False,
				'Could not change email of user %s: %s' % (user.name, str(e)))
  
	def setFullName(self, req, user):
		try:
			user.fullname = uc_str(req.post.get('fullname'))
			return XMLStatusResponse('setFullName', True,
				'Changed name for user %s to %s' %
				(user.name, user.fullname))
		except validators.InvalidFullname, e:
			return XMLStatusResponse('setFullName', False, str(e))
		except Exception, e:
			return XMLStatusResponse('setFullName', False,
				'Could not change name of user %s: %s' % (user.name, str(e)))

	def setPassword(self, req, user):
		try:
			user.set_password(req.post.get('password'))
			return XMLStatusResponse('setPassword', True,
				'Changed password for user %s' % user.name)
		except Exception, e:
			return XMLStatusResponse('setPassword', False,
				'Could not change password of user %s: %s' % (user.name, e))

	@admin_required
	def addToGroup(self, req, user):
		group = Group(req.post.get('addToGroup'))
		success = True
		try:
			group.add_member(user)
		except MemberExistsError:
			success = False

		msgs = {True: 'User %s added to group %s' % (user.name, group.name),
				False: 'User %s already in group %s' % (user.name, group.name)
				}
		return XMLStatusResponse('addToGroup', success, msgs[success])

	def listUserGroups(self, req, user):
		member_of_names = list(user.member_of())
		session_user = req.session['user']
		if session_user.is_admin:
			nonmember_of = []
			groupnames = Group.list(session_user)
			for groupname in groupnames:
				if groupname not in member_of_names:
					nonmember_of.append(groupname)
			
			return XMLTemplateResponse("ajax/usermemberof.xml",
					{"memberof": member_of_names,
						"nonmemberof": nonmember_of, "user": user.name})

		if req.session['user'].name != user.name:
			return XMLStatusResponse('listUserGroups', False, "You do not have permission to "
					"view this user.")

		return XMLTemplateResponse("ajax/usermemberof.xml",
				{"memberof": member_of_names, "nonmemberof": [],
					"user": user.name})

	def listNotifications(self, req, user):
		session_user = req.session['user']
		if not session_user.is_admin and session_user.name != user.name:
			return XMLStatusResponse('listNotifications', False, "You do not have permission to "
					"view this user.")

		# rebuild notifications into a list so we can sort it
		notifications = []
		for (name, d) in user.notifications().iteritems():
			# add a 'name' key, leave the 'allowed' and 'enabled' keys
			d['name'] = name
			notifications.append(d)

		# sort on name
		notifications.sort(cmp=lambda x,y: cmp(x['name'], y['name']))

		return XMLTemplateResponse("ajax/usernotifications.xml",
				{"notifications": notifications, "username": user.name,
				"session_user": session_user})

	def saveNotifications(self, req, user):
		session_user = req.session['user']
		
		notifications_str = req.post.get('saveNotifications').split(':')
		notifications = {}
		for n_str in notifications_str:
			n = n_str.split(',')
			if len(n) < 2:
				return XMLStatusResponse('saveNotifications', False, 'badly formatted notifications')
			try:
				allowed = (n[1] == "true")
				enabled = (n[2] == "true")
				user.set_notification(n[0], allowed, enabled, session_user)
			except UserPermissionError, e:
				return XMLStatusResponse('saveNotifications', False, str(e))

		return XMLStatusResponse("saveNotifications", True, "Saved notifications for user " + user.name)

	@admin_required
	def removeFromGroup(self, req, user):
		group = Group(req.post.get('removeFromGroup'))
		success = True
		try:
			group.remove_member(user)
		except: # XXX except what?!
			succes = False

		msgs = {True: 'User %s removed from group %s' % (user.name, group.name),
				False: 'User %s is not a member of %s' % (user.name, group.name)
				}
		return XMLStatusResponse('removeFromGroup', success, msgs[success])

	@admin_required
	def removeUser(self, req, username):
		if username == req.session['user'].name:
			return XMLStatusResponse('removeUser', False,
				'You are not allowed to delete yourself')
		try:
			user = User(username)
			user.remove()
		except Exception, e:
			return XMLStatusResponse('removeUser', False,
				'User %s not deleted: %s' % (username, str(e)))

		return XMLStatusResponse('removeUser', True, 'User %s deleted' % username)

	@admin_required
	def setIsAdmin(self, req, user):
		is_admin = req.post.get('setIsAdmin')
		if user.name == req.session['user'].name:
			return XMLStatusResponse('setIsAdmin', False,
				'You are not allowed to change admin rights for yourself')

		try:
			user.is_admin = is_admin
		except Exception, e:
			return XMLStatusResponse('setIsAdmin', False,
				'Could not change admin status for user %s: %s' % (user.name, str(e)))

		newstatus = {'false':'revoked', 'true':'granted'}[is_admin]
		return XMLStatusResponse('setIsAdmin', True, 
			'Admin rights for user %s %s' % (user.name, newstatus))