from submin.path.path import Path
from submin.models.exceptions import StorageAlreadySetup
import os, sys

class c_config():
	'''Commands to change config
Usage:
	config defaults                 - create config with defaults
	config get                      - list everything
	config get <option>             - get config value in section
	config set <option> <value>     - set config value in section'''

	needs_env = False

	def __init__(self, sa, argv):
		self.sa = sa
		self.argv = argv
		self.settings_path = str(Path(self.sa.env) + 'conf' + 'settings.py')

	def subcmd_defaults(self, argv):
		self.settings_defaults(self.settings_path)

	def _printkeyvalue(self, options, key, value, width):
		formatstring = "%%-%us %%s" % (width + 1)
		print formatstring % (key, value)

	def subcmd_get(self, argv):
		self.sa.ensure_storage()

		import submin.models.options
		o = submin.models.options.Options()
		if len(argv) == 1:
			value = o.value(argv[0])
			self._printkeyvalue(o, argv[0], value, len(argv[0]))
		else:
			options = o.options()
			options.sort()
			maxlen = 0
			for arg in options:
				if len(arg[0]) > maxlen: maxlen = len(arg[0])

			for arg in options:
				self._printkeyvalue(o, arg[0], arg[1], maxlen)

	def subcmd_set(self, argv):
		self.sa.ensure_storage()

		if len(argv) != 2:
			self.sa.execute(['help', 'config'])
			return

		import submin.models.options
		o = submin.models.options.Options()
		o.set_value(argv[0], argv[1])

	def session_salt(self):
		import random
		salts = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789./'
		salt = ''
		rand = random.Random()
		for i in range(16):
			salt += rand.choice(salts)

		return salt

	def vcs_plugins(self):
		import pkgutil, os
		# __file__ returns <submin-dir>/subminadmin/c_config.py
		libdir = os.path.dirname(os.path.dirname(__file__))
		vcsdir = os.path.join(libdir, 'plugins', 'vcs')
		return [name for _, name, _ in pkgutil.iter_modules([vcsdir])]

	def settings_defaults(self, filename):
		# write the bootstrap settings file
		submin_settings = '''
import os
storage = "sql"
sqlite_path = os.path.join(os.path.dirname(__file__), "submin.db")
'''

		dirname = os.path.dirname(filename)
		try:
			os.makedirs(dirname)
		except OSError, e:
			if e.errno == 17: # file exists
				pass

		file(filename, 'w').write(submin_settings)

		# after writing the bootstrap file, we setup all models
		self.sa.ensure_storage()
		from submin.models import storage
		try:
			storage.setup()
		except StorageAlreadySetup:
			pass # silently ignore and continue setting defaults

		# And now we can use the models
		#from models.options import Options
		import submin.models.options

		o = submin.models.options.Options()
		http_base = ''
		options = {
			'base_url_submin': http_base + '/submin',
			'base_url_svn': http_base + '/svn',
			'base_url_trac': http_base + '/trac',
			'auth_type': 'sql',
			'svn_dir': 'svn',
			'trac_dir': 'trac',
			'dir_bin': 'static/bin',
			'enabled_trac': 'no',
			'session_salt': self.session_salt(),
			'env_path': '/bin:/usr/bin:/usr/local/bin:/opt/local/bin',
			'vcs_plugins': ','.join(self.vcs_plugins()),
		}
		for (key, value) in options.iteritems():
			o.set_value(key, value)

	def run(self):
		if len(self.argv) < 1:
			self.sa.execute(['help', 'config'])
			return

		try:
			subcmd = getattr(self, 'subcmd_%s' % self.argv[0])
		except AttributeError:
			self.sa.execute(['help', 'config'])
			return

		subcmd(self.argv[1:])