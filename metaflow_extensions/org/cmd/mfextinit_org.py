from metaflow.extension_support.cmd import process_cmds_description

# EXAMPLE: Add a new command to the metaflow command-line tool
CMDS_DESC = [("specialcommand", ".special_command.cli")]

# Do *NOT* forget this line
process_cmds_description(globals())
