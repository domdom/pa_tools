from collections import OrderedDict

from pa_tools.pa import pajson
from pa_tools.pa.paths import PA_MEDIA_DIR

from posixpath import normpath

class ModReport:
    def __init__(self, mod_path):
        self.mod_path = mod_path
        self.mod_root = mod_path
        self.modinfo = None
        self.modinfo_issues = []
        self.file_issues = OrderedDict()
        self.json_issues = OrderedDict()


    def addInfoIssue(self, issue):
        self.modinfo_issues.append(issue)

    def addJsonIssue(self, json_file, issues):
        if len(issues) == 0:
            return
        if json_file in self.json_issues:
            self.json_issues[json_file] |= set(issues)
        else:
            self.json_issues[json_file] = set(issues)

    def addFileIssue(self, file_name, referenced_by):
        if isinstance(referenced_by, list):
            ref_set = set(referenced_by)
        elif isinstance(referenced_by, str):
            ref_set = set([referenced_by])

        if file_name in self.file_issues:
            self.file_issues[file_name] |= ref_set
        else:
            self.file_issues[file_name] = ref_set

    def getIssueCount(self):
        return self.getJsonIssueCount() + self.getFileIssueCount() + self.getInfoIssueCount()
    def getJsonIssueCount(self):
        return sum(len(x) for x in self.json_issues.values())
    def getFileIssueCount(self):
        return len(self.file_issues)
    def getInfoIssueCount(self):
        return len(self.modinfo_issues)

    def printDetailsReport(self):
        report = _make_heading('MOD DETAILS', '=')
        if self.modinfo is not None:
            report += _line('      name: ' + self.modinfo['display_name'])
            report += _line('identifier: ' + self.modinfo['identifier'])
            report += _line('    author: ' + self.modinfo['author'])
            report += _line('     forum: ' + self.modinfo['forum'])
        else:
            report += _line('    <failed to load modinfo>')
        report += _line()
        return report

    def printFileIssueReport(self):
        # missing file issues
        report = _make_heading('MISSING FILES ' + str(self.getFileIssueCount()), '-')
        for file, refs in self.file_issues.items():
            report += _line('' + file)
            for ref in refs:
                report += _line('      referenced by ' + normpath(ref))
        report += _line()
        return report

    def printJsonIssueReport(self):
        # json parsing issues
        report = _make_heading('JSON ISSUES ' + str(self.getJsonIssueCount()), '-')
        for issues in self.json_issues.values():
            for json_issue in issues:
                report += _line(json_issue)
            report += _line()

        report += _line()
        return report

    def printInfoIssueReport(self):
        # listing issues with the modinfo files
        report = _make_heading('MODINFO ISSUES ' + str(self.getInfoIssueCount()), '-')
        for modinfo_issue in self.modinfo_issues:
            report += _line(modinfo_issue)
        report += _line()
        return report

    def printReport(self):
        report = ''
        # basic details about the mod
        report += self.printDetailsReport()

        # summary
        report += _make_heading('ISSUE SUMMARY ' + str(self.getIssueCount()), '-')
        report += _line('modinfo issues: ' + str(self.getInfoIssueCount()))
        report += _line(' missing files: ' + str(self.getFileIssueCount()))
        report += _line('   json issues: ' + str(self.getJsonIssueCount()))
        report += _line()

        report += self.printInfoIssueReport()
        report += self.printFileIssueReport()
        report += self.printJsonIssueReport()

        return report

def _make_heading(heading, underline_character): return heading + '\n' + underline_character * len(heading) + '\n'
def _line(string=''): return string + '\n'

def find_missing_files(mod_report, loader):
    visited = set()
    file_path = '/pa/units/unit_list.json'
    referenced_by = ''

    _walk_json(mod_report, loader, visited, file_path, referenced_by)


def _walk_json(mod_report, loader, visited, file_path, referenced_by):
    visited.add(file_path)

    resolved_file = loader.resolveFile(file_path)
    if resolved_file is None:
        mod_report.addFileIssue(file_path, referenced_by)
        return

    if not file_path.endswith('.json') and not file_path.endswith('.pfx'):
        return

    with open(resolved_file, 'r', encoding='utf-8') as file:
       obj, warnings = pajson.load(file)

    if len(warnings) > 0:
        mod_report.addJsonIssue(file_path, warnings)

    file_list = _walk_obj(obj)
    for file in file_list:
        if file not in visited:
            _walk_json(mod_report, loader, visited, file, resolved_file)

def check_mod(mod_path):
    from pa_tools.pa import pafs
    from os.path import join, dirname

    mod_report = ModReport(mod_path)

    mod_report.mod_root = _find_mod_root(mod_report.mod_path)
    if mod_report.mod_root is None:
        mod_report.addInfoIssue('FATAL: Could not find modinfo.json')
        return mod_report

    loader = pafs(mod_report.mod_root)

    modinfo_path = loader.resolveFile('/modinfo.json')
    if modinfo_path is None:
        mod_report.addInfoIssue('FATAL: Could not find modinfo.json')
        return mod_report

    check_modinfo(mod_report, modinfo_path, loader)
    if mod_report.modinfo is None:
        return mod_report

    # construct loader for checking files

    loader = pafs(PA_MEDIA_DIR)
    is_classic_only = mod_report.modinfo.get('classicOnly', False)
    is_titans_only = mod_report.modinfo.get('titansOnly', False)
    if is_titans_only or not is_classic_only:
        loader.mount('/pa', '/pa_ex1')
    loader.mount('/', mod_report.mod_root)

    find_missing_files(mod_report, loader)

    return mod_report

def check_modinfo(mod_report, modinfo_path, loader):
    with open(modinfo_path, 'r', encoding='utf-8') as file:
       modinfo, warnings = pajson.load(file)
    mod_report.addJsonIssue(modinfo_path, warnings)

    mandatory_fields = [
        'author',
        'build',
        'category',
        'context',
        'date',
        'description',
        'display_name',
        'forum',
        'identifier',
        'signature',
        'version'
    ]

    if modinfo is None:
        mod_report.addInfoIssue('FATAL: Could not parse modinfo.json')
        return

    new_modinfo = {}
    for key, value in modinfo.items():
        new_modinfo[key.lower()] = value
    modinfo = new_modinfo


    for field in mandatory_fields:
        field_value = modinfo.get(field, None)

        if field_value == '':
            mod_report.addInfoIssue('ERROR: Mandatory field "'+field+'" is empty.')
        if field_value is None:
            field_value = ''
            mod_report.addInfoIssue('ERROR: Mandatory field "'+field+'" is missing.')

        modinfo[field] = field_value


    # build - string - mandatory, build number
    category = modinfo.get('category', None)
    if category == []:
        mod_report.addInfoIssue('WARNING: "category" field is empty. Use category keywords to make your mod easier to search for.')
    elif isinstance(category, list):
        redundant_keywords = set(['mod', 'client', 'client-mod', 'server', 'server-mod'])
        prefered_keyword_mapping = {
            'map': 'maps',
            'planet': 'maps',
            'planets': 'maps',
            'system': 'maps',
            'systems': 'maps',

            'texture':'textures',
            'unit': 'units',
            'buildings':'units',
            'particle': 'effects',
            'effect': 'effects',
            'live-game': 'gameplay',
            'in-game': 'gameplay',
            'strategic-icons': 'icons',
            'strategic icons': 'icons',
            'icon': 'icons',

            'bug-fix': 'fix',
            'bugfix': 'fix',
            'hot-fix': 'fix',
            'hotfix': 'fix'
        }
        for item in category:
            if not isinstance(item, str):
                mod_report.addInfoIssue('ERROR: "category" array contains a non-string element: ' + str(item))
            else:
                if item.lower() in redundant_keywords:
                    mod_report.addInfoIssue('WARNING: "category" array contains a redundant entry: '+ item +'. Please remove this entry.')
                if item.lower() in prefered_keyword_mapping:
                    mod_report.addInfoIssue('WARNING: "category" array contains a redundant entry: '+ item +'. Please use "' + prefered_keyword_mapping[item.lower()] + '" instead.')
    elif category is not None:
        mod_report.addInfoIssue('ERROR: "category" field must be an array of strings.')

    
    # context - string - mandatory, server or client
    context = modinfo.get('context', None)
    if context not in ['client', 'server']:
        mod_report.addInfoIssue('ERROR: "context" is must be either "client", or "server".')


    # store reference to the modinfo
    mod_report.modinfo = modinfo


def _parse_spec(spec_path):
    ret = set()
    specs = spec_path.split(' ')
    for spec in specs:
        if '/' in spec and '.' in spec and spec.find('/') < spec.find('.'):
            ret.add(spec)

    return ret


def _walk_obj(obj):
    if isinstance(obj, str):
        return _parse_spec(obj)

    specs = set()
    if isinstance(obj, dict):
        obj = list(obj.values())

    if isinstance(obj, list):
        specs = set()
        for value in obj:
            specs |= _walk_obj(value)

    return specs


def _find_mod_root(mod_path):
    from os.path import join, dirname
    from glob import glob

    glob_result = glob(join(mod_path, '**','modinfo.json'), recursive=True)

    if len(glob_result) == 1:
        return dirname(glob_result[0])
    else:
        return None




"""
        145 in-game
        131 ui
        52 titans
        45 texture
        28 shader
        27 server-mod
        26 maps
        25 effects
        23 units
        21 client-mod
        18 strategic-icons
        18 planets
        17 lobby
        16 map
        15 systems
        15 pack
        15 planet
        15 system
        13 colours
        13 galactic-war
        12 explosion
        11 system-editor
        9 framework
        8 biome
        7 classic
        7 game-mode
        7 cheat
        7 metal
        7 balance
        7 bugfix
        7 strategic icons
        6 commander
        6 hearts
        6 modding
        5 sandbox
        5 chat
        4 main-menu
        4 reclaim
        4 ai
        4 uberbar
        3 system editor
        3 gameplay
        3 energy
        3 bug-fix
        3 appearance
        2 settings
        2 economy
        2 racing
        2 mex
        2 artillery
        2 player-guide
        2 particles
        2 buildings
        2 ai-skirmish
        2 nuke
        1 lana
        1 tweak
        1 twitch
        1 landmines
        1 pip
        1 features
        1 projectiles
        1 client
        1 game
        1 anti-nuke
        1 sound
        1 server
        1 performance
        1 energy plant
        1 icons
        1 combat
        1 violet
        1 alerts
        1 water
        1 tropical
        1 naval
        1 soundtrack
        1 mod-help
        1 the
        1 wpmarshall
        1 filter
        1 stars
        1 icon
        1 reference
        1 scale
        1 ania
        1 live-game
        1 violetania
        1 marshall
        1 selection
        1 chrono-cam
        1 replay browser
        1 system_editor
        1 construction
        1 antinuke
        1 trails
        1 anti
        1 background
        1 tournaments
        1 model
        1 hotfix
        1 series
        1 textures
        """
