#!/usr/bin/env python
import argparse
import os
import subprocess
import re
import sys
import itertools
import os.path

def readCL():
    parser = argparse.ArgumentParser()
    parser.add_argument("--infile", default="Snakefile")
    parser.add_argument("-v","--verbose",action="store_true")
    parser.add_argument("-p","--print_all",action="store_true")
    parser.add_argument("rules", nargs="*")
    args = parser.parse_args()
    return args.infile, args.verbose, args.print_all, args.rules
    

class Singleton(type):
    """
    metaclass singleton pattern from 
    http://stackoverflow.com/questions/6760685/creating-a-singleton-in-python
    """
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class DependencyGraphSingleton(object):
    __metaclass__ = Singleton
    def __init__(self):
        self._rules = []
        self._required_in_nodes = set()
        self._forward_edges = {}
        self._backward_edges = {}
    def setup(self, snake_dir):
        self.snake_dir = snake_dir
    def add_rule(self, rule):
        self._rules.append(rule)
        out_nodes = rule.out_nodes()
        for n in out_nodes:
            if n in self._backward_edges:
                raise Exception("ERROR: output file {n} listed in multiple rules".format(**vars()))
            self._backward_edges[n] = rule
    def process_all(self):
        for r in self._rules:
            if self.check_timestamp(r) or any([i in force_list for i in self._required_in_nodes]):
                r.execute()
                self._required_in_nodes.update(r.in_nodes())
    def backward_edges(self):
        return self._backward_edges
    def rules(self):
        return self._rules
    def check_timestamp(self, rule):
        for f in rule.in_nodes():
            if not os.path.exists(f) and not f in self.backward_edges():
                raise Exception("ERROR: can't find input file {f}".format(**vars()))
        if any([not os.path.exists(f) for f in rule.all_nodes()]):
            return True
        outputs = rule.out_nodes()
        min_out_time = min([os.path.getmtime(f) for f in outputs] + [1e20]) #default 1e20

        inputs = rule.in_nodes()
        max_in_time = max([os.path.getmtime(f) for f in inputs] +     [-1]) #default -1
        if max_in_time > min_out_time or rule.cmd_cache_stale():
            return True
        else:
            return False
        

def run(cmd):
    import subprocess
    pipes = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    stdout, stderr = pipes.communicate()
    return_code = pipes.returncode
    return stdout, stderr, return_code


class Rule(object):
    def __init__(self, out_nodes, in_nodes, cmd):
        self._out_nodes = out_nodes
        self._in_nodes = in_nodes
        set_variables_cmd = " ".join(["INPUT{i}={var};".format(**vars()) for i,var in enumerate(self._in_nodes)]) + " " +\
                            " ".join(["OUTPUT{i}={var};".format(**vars()) for i,var in enumerate(self._out_nodes)])
        cmd = set_variables_cmd + '\n' + cmd
        self._cmd = cmd
    def cmd_file(self):
        #write the cmd if changed
        out_hash = abs(hash(tuple(self.out_nodes())))
        snake_dir = DependencyGraphSingleton().snake_dir
        cache_file = "{snake_dir}/cmd_{out_hash}".format(**vars())
        return cache_file
    def cmd_cache_stale(self):
        cache_file = self.cmd_file()
        return not os.path.exists(cache_file) or self.cmd() != open(cache_file).read()
    def cache_cmd(self):
        cache_file = self.cmd_file()
        if self.cmd_cache_stale():
            with open(cache_file, 'w') as f_out:
                f_out.write(self.cmd())
    def execute(self):
        # print "Executing",self._in_nodes, self._out_nodes
        # print self._cmd
        self.cache_cmd()
        return run(self._cmd)
    def in_nodes(self):
        return self._in_nodes
    def out_nodes(self):
        return self._out_nodes
    def all_nodes(self):
        return set(self._in_nodes).union(set(self._out_nodes))
    def cmd(self):
        return self._cmd
    def __str__(self):
        return ", ".join(self._out_nodes) + " <- " + ", ".join(self._in_nodes)


def define_rule(outfiles, infiles, cmd):
    #remove symlinks
    outfiles = [os.path.realpath(f) for f in outfiles]
    infiles = [os.path.realpath(f) for f in infiles]
    graph = DependencyGraphSingleton()
    rule = Rule(outfiles, infiles, cmd)
    graph.add_rule(rule)

def get_all(force=False):
    graph = DependencyGraphSingleton()
    nodes_to_update = set()
    required_rules = []
    for r in graph.rules():
        if graph.check_timestamp(r) or force or nodes_to_update.intersection(set(r.in_nodes())):
            nodes_to_update.update(r.out_nodes())
            required_rules.append(r)
    return required_rules


def get_upstream(base_node, force=False):
    graph = DependencyGraphSingleton()
    upstream_nodes = set([base_node])
    for r in graph.rules()[::-1]:
        if upstream_nodes.intersection(set(r.out_nodes())):
            upstream_nodes.update(r.in_nodes())
    nodes_to_update = set()
    required_rules = []
    for r in graph.rules():
        if upstream_nodes.intersection(set(r.out_nodes())):
            if graph.check_timestamp(r) or force or nodes_to_update.intersection(set(r.in_nodes())):
                nodes_to_update.update(r.out_nodes())
                required_rules.append(r)
    return required_rules


def get_downstream(base_node, force=False):
    graph = DependencyGraphSingleton()
    downstream_nodes = set([base_node])
    for r in graph.rules():
        if downstream_nodes.intersection(set(r.in_nodes())):
            downstream_nodes.update(r.out_nodes())
    nodes_to_update = set()
    required_rules = []
    for r in graph.rules():
        if downstream_nodes.intersection(set(r.in_nodes())):
            if graph.check_timestamp(r) or force or nodes_to_update.intersection(set(r.in_nodes())):
                nodes_to_update.update(r.out_nodes())
                required_rules.append(r)
    return required_rules


def get_exact(base_node, force=False):
    graph = DependencyGraphSingleton()
    required_rules = []
    for r in graph.rules():
        if (base_node in r.out_nodes()) and (graph.check_timestamp(r) or force):
            required_rules.append(r)
    return required_rules


def get_required_rules(expression):
    force = expression.startswith("+")
    regex_match = re.findall("^(\+?(\^|=)?)(.*)",expression)[0]
    prefix, body = regex_match[0], regex_match[2]
    body = os.path.realpath(body)
    force = prefix.startswith("+")
    exact = "=" in prefix
    downstream = "^" in prefix
    upstream = not "^" in prefix
    if exact:
        return get_exact(body, force)
    elif upstream:
        return get_upstream(body, force)
    elif downstream:
        return get_downstream(body, force)
    else:
        raise Exception("ERROR: couldn't parse expression {expression}".format(**vars()))


def sort_rules(rule_set):
    graph = DependencyGraphSingleton()
    for r in graph.rules():
        if r in rule_set:
            yield r


def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = itertools.tee(iterable)
    next(b, None)
    return itertools.izip(a, b)


def list_condition_blocks(l, fn):
    """
    Args:
      l: list
      fn: function acting on elements of l

    Returns:
      a list of lists. sublists are consecutive elements
      from l with the same fn value

    Example:
    list_condition_blocks(["a","b","abc","d","e"],len)
    returns
    [["a","b"],["abc"],["d","e"]]
    """
    x1 = l[0]
    blocks = [[x1]]
    for x1,x2 in pairwise(l):
        if x1 == None:
            raise Exception("ERROR: can't have None elements in l")
        if (x2 != None) and fn(x2) == fn(x1):
            blocks[-1].append(x2)
        else:
            blocks.append([x2])
    return blocks


    

def preprocess_snakefile(snakefile_string):
    def indent_depth(x):
        return len(x) - len(x.lstrip())

    def is_rule_def(x):
        return "<-" in x

    def subtract_indent_depth(x, depth):
        """
        Remove leading whitespace up to 'depth'
        """
        return x[depth:]

    def preprocess_bash(bash_str):
        """
        replace $[var] with eval(var)
        """
        regex1 = "(\$\[.*?\])"
        regex2 = "\$\[(.*?)\]"
        out = ""
        for piece in re.split(regex1, bash_str):
            match = re.findall(regex2, piece)
            if match:
                out += "+ str({0}) +".format(match[0])
            else:
                #use repr so when python exec's the code later it gets back the original string
                out += repr(piece)
        return out

    def take_all_rule_blocks(l):
        """
        take_fn(l) --> block, remaining_list

        take_chunks(l, take_fn) --> [block]
        """
        while l:
            block, l = take_rule_block(l)
            yield block


    def take_rule_block(l):
        block = [l[0]]
        if "<-" in l[0]:
            rule_depth = indent_depth(l[0])
            for i in l[1:]:
                depth_i = indent_depth(i)
                if "<-" in i or depth_i <= rule_depth:
                    break
                else:
                    block.append(i)
        else:
            for i in l[1:]:
                if "<-" in i:
                    break
                else:
                    block.append(i)
        block_len = len(block)
        return block, l[block_len:]

    def process_rule_string(rule_string):
        options = re.findall("\[(.*)\]\s*$",rule_string)
        if options:
            outputs, inputs, options = re.findall("(^.*)<-(.*)\[(.*)\]\s*$",rule_string)[0]
        else:
            outputs, inputs = re.findall("(^.*)<-(.*$)",rule_string)[0]
        outputs = [(o.strip()) for o in outputs.split(",")]
        inputs = [(i.strip()) for i in inputs.split(",")]
        if options:
            options = options.split()
            options = dict([(l.split(":")[0],l.split(":")[1]) for l in options])
        return outputs, inputs, options

    lines = snakefile_string.split('\n')
    lines = [l for l in lines if not l.strip().startswith("#")] #remove comments (TODO: handle comments at the end of lines
    indent_levels = list_condition_blocks(lines, is_rule_def)
    skip = False
    for block in take_all_rule_blocks(lines):
        if "<-" in block[0]:
            outputs, inputs, options = process_rule_string(block[0])
            if "cmd" in options:
                cmd_str = options["cmd"]
            elif len(block) > 1:
                depth = indent_depth(block[1])
                cmd_str = preprocess_bash('\n'.join([subtract_indent_depth(l,depth) for l in block[1:] if l]))
            else:
                raise Exception("ERROR: parser couldn't find provided command!")
            outputs_string = "[" + ",".join(outputs) + "]"
            inputs_string = "[" + ','.join(inputs) + "]"
            leading_whitespace = re.findall("^\s*",block[0])[0]
            yield leading_whitespace + """define_rule({outputs_string},{inputs_string},{cmd_str})""".format(**vars())
        else:
            for l in block:
                yield l


                
def y_n_input(message):
    out = raw_input(message)
    while True:
        if out.lower() == "y":
            return True
        elif out.lower() == "n":
            return False
        else:
            out = raw_input("Please input y or n" + '\n')

def get_snake_dir(infile):
    infile_absolute_path = os.path.abspath(infile)
    infile_dir = os.path.dirname(infile_absolute_path)
    snake_dir = infile_dir + "/.snake"
    return snake_dir
            

if __name__ == "__main__":
    infile, verbose, print_all, args = readCL()

    snake_dir = get_snake_dir(infile)
    if not os.path.exists(snake_dir):
        os.mkdir(snake_dir)

    # print args
    with open(infile) as f_in:
        parsed = '\n'.join(list(preprocess_snakefile(f_in.read())))
        # print parsed
        exec(parsed)

    #initialize DependencyGraph:
    graph = DependencyGraphSingleton()
    graph.setup(snake_dir)

    if print_all:
        for i,r in enumerate(graph.rules()):
            print "  " + str(i+1)+":" + " " + str(r)
        sys.exit(0)
            

    if not args:
        required_rules = get_all() #graph.process_all()
    else:
        required_rules = set([r for a in args for r in get_required_rules(a)])
        
    required_rules = list(sort_rules(required_rules))

    if not required_rules:
        print "Nothing to do."
        sys.exit(-1)


    print "The following steps will be run, in order:"
    for i,r in enumerate(required_rules):
        print "  " + str(i+1)+":" + " " + str(r)

    if not y_n_input("Confirm? [y/n]" + '\n'):
        print "Exiting..."
        sys.exit(-1)

    for r in required_rules:
        print "Running: ", r, '\n'
        if verbose:
            print r.cmd()
        sydout, stderr, return_code = r.execute()
        if return_code != 0:
            sys.stderr.write("ERROR in command: \n" + r.cmd() + '\n\n' + stderr + '\n')
            if y_n_input("Erase output files from step that errored? [y/n]" + '\n'):
                for n in r.out_nodes():
                    print "Removing... ", n
                    os.remove(n)
            sys.exit(-1)

