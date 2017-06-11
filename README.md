Snake is a script for managing programming workflow dependencies. It's an attempt at a port of Factual's drake (https://github.com/Factual/drake) to Python.

## Quick Start
1) pip install python-snake
2) Create a file named Snakefile in the directory of the data workflow.
3) Run the snake command in the data workflow directory to execute the Snakefile

## Basic Description
Consider a simple data pipeline.
Starting from input file "a.txt", you run "script1.py" to generate "b.txt".
Then you run "script2.py" on "b.txt" to generate "c.txt"

The Snakefile stores the steps of the data pipeline along with the dependencies of each step. Running the 'snake' command executes the Snakefile, which checks which rules should be run and then carries out those steps.
For example, if "a.txt" has been recently modified both "script1.py" and "script2.py" should be executed.
In the case that you already ran "script1.py" last night, but not "script2.py", then snake will find that "b.txt" is newer than "c.txt" and only the "script2.py" step should run.

Other common use cases include running all steps necessary to generate a specific file, running all steps that depend on a specific file, and forcing a specific step to rerun even if the input file hasn't been modified.

## Basic Snakefile Syntax
The Snakefile holds the information about the data pipeline. It consists of a list of dependency rules and the bash commands they entail.

Example rule:
```
"b.txt" <- "a.txt"
    echo "test"; cat a.txt > b.txt
```
The first line is the header. A file named "b.txt" depends on a file named "a.txt".
The second line (and any subsequent lines, which are indented) is the body. When the rule is triggered this shell command is executed.

Example rule #2:
```
"c.txt", "d.txt" <- "b.txt", "a.txt"
    cp a.txt c.txt
    cp b.txt d.txt
```
Here the header shows that "c.txt" and "d.txt" depend on "b.txt" and "a.txt". When the rule is triggered, a.txt and b.txt are copied into c.txt and d.txt.

## Running the snake command
Running
```
snake
```
Will look for a Snakefile in the current directory and execute all rules necessary

A common use case to run only the steps necessary to update a given file.
```
snake /tmp/atp_players.csv
```

Use '+' to force rerun all steps that generate a file
```
snake +/tmp/atp_players.csv
```

Use '=' to consider only the rule that directly generates the file (not other rules upstream)
```
snake =/tmp/atp_players.csv
```

Use '^' to run all steps that depend (directly or indirectly) on a file. That is, run the pipeline downstream from this file.
```
snake ^/tmp/atp_players.csv
```

Use '@' to search for files that match a regex
```
snake +@atp_players
```

The order of operations of the above is +=@. Use all three to force the rule that directly generates the file matched by the regex
```
snake +=@atp_players
```

## Arguments

-v
  Verbose. Prints the reason for running each step, along with information about the commands run at each step

-p
  Print every step, but don't run any

-f
  Specify a Snakefile file (default is "./Snakefile")

```
snake -f scripts/Snakefile
```

## More advanced examples (incomplete)

basic_cmd = """(echo "test"; cat $INPUT0) > $OUTPUT0"""

"v5.txt" <- "v1.txt", "v2.txt" [cmd:basic_cmd]
"v6.txt" <- "v3.txt", "v4.txt" [cmd:basic_cmd]
"v7.txt" <- "v5.txt", "v6.txt" [cmd:basic_cmd]
"v8.txt", "v9.txt" <- "v7.txt" [cmd:basic_cmd]
"v10.txt", "v11.txt" <- "v8.txt" [cmd:basic_cmd]
"v12.txt", "v13.txt" <- "v9.txt" [cmd:basic_cmd]

for i in range(1,6):
    next = i+1
    output = "n{next}.txt".format(**vars())
    input = "n{i}.txt".format(**vars())
    output <- input
        (echo "test"; cat $INPUT0) > $OUTPUT0
