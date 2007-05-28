import os

from library import Library
from template import Template
register = Library()

DEBUG = True

def d(*msgs):
	if DEBUG:
		print '*** DEBUG:', ' '.join([str(msg) for msg in msgs])

class ElseError(Exception):
	pass

class UnknownTemplateError(Exception):
	pass

class MissingRequiredArguments(Exception):
	pass


@register.register('set')
def set(node, tpl):
	"""Sets a variable to a value, local to the template.
	Don't use a period (.) in your variable-name, because the [val] tag will
	not like that."""
	text = node.nodes[0].evaluate()
	args = node.arguments
	if not args:
		raise MissingRequiredArguments, \
			"Missing required argument variable on line %d" % node.line
	
	d('set variable %s to %r' % (args, text))
	tpl.variables[args] = text
	return ''

@register.register('val')
def val(node, tpl):
	if not node.nodes:
		raise MissingRequiredArguments, \
			"Missing required argument variable on line %d" % node.line
		
	text = node.nodes[0].evaluate()
	d("get variable_value of %r" % text)
	if not text:
		raise MissingRequiredArguments, \
			"Missing required argument variable on line %d" % node.line
	value = tpl.variable_value(text)
	if value:
		return str(value)
	return ''

@register.register('include')
def include(node, tpl):
	to_include = node.nodes[0].evaluate()
	d('including %s!' % to_include)
	
	if not os.path.exists(to_include):
		raise UnknownTemplateError, "Could not find '%s' (line %d)" % (to_include, node.line)
	oldcwd = os.getcwd()
	if os.path.dirname(to_include):
		os.chdir(os.path.dirname(to_include))
	
	fp = open(os.path.basename(to_include), 'r')
	evaluated_string = ''
	if fp:
		lines = ''.join(fp.readlines())
		new_tpl = Template(lines, tpl.variables)
		evaluated_string = new_tpl.evaluate()
		
		fp.close()
	if os.path.dirname(to_include):
		os.chdir(oldcwd)
	return evaluated_string
	
@register.register('iter')
def iter(node, tpl):
	d('Iterate over', node.arguments)
	
	if not node.arguments:
		raise MissingRequiredArguments, \
			"Missing required argument variable on line %d" % node.line
	
	if not tpl.node_variables.has_key('ival'):
		tpl.node_variables['ival'] = []
	tpl.node_variables['ival'].append(None)
	
	value = ''
	if node.arguments.startswith('ival'):
		if node.arguments == 'ival':
			value = tpl.node_variables['ival'][-2]
			d('ival = %r' % value)
		else:
			# take from ival.foo.bar the foo.bar part
			args = node.arguments.split('.', 1)[1]
			if len(tpl.node_variables['ival']) >= 1:
				value = tpl.variable_value('', args, tpl.node_variables['ival'][-2])
				d('ival.args = %r' % value)
	else:
		value = tpl.variable_value(node.arguments)
	evaluated_string = ''
	if not value:
		return ''
	for item in value: #tpl.variables[node.arguments]:
		tpl.node_variables['ival'][-1] = item
		evaluated_string += ''.join([x.evaluate(tpl) for x in node.nodes])
	tpl.node_variables['ival'].pop()
	return evaluated_string

@register.register('ival')
def ival(node, tpl):
	args = node.arguments
	if not args:
		args = None
	if len(tpl.node_variables['ival']) >= 1:
		return str(tpl.variable_value('', args, tpl.node_variables['ival'][-1]))
	return ''

@register.register('test')
def test(node, tpl):
	d('Test if %s is set!' % node.arguments)
	if not node.arguments:
		raise MissingRequiredArguments, \
			"Missing required argument variable at line %d" % node.line
	value = tpl.variable_value(node.arguments)
	if value is None or not value:
		return ''
	return ''.join([x.evaluate(tpl) for x in node.nodes])

@register.register('else')
def else_tag(node, tpl):
	d('Else!')
	prev = node.previous_node
	if prev.type == 'text' and prev.content.isspace():
		prev = prev.previous_node
	d("Else's previous_node: %s" % prev)
	if prev.type != 'command' or prev.command != 'test':
		raise ElseError, 'Previous node to else was not a test-node (line %d)!' % node.line
	value = tpl.variable_value(prev.arguments)
	if value is None or not value:
		return ''.join([x.evaluate(tpl) for x in node.nodes])
	return ''