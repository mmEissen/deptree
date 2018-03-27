import abc
import argparse
import builtins
import sys
from types import ModuleType
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Callable

from graphviz import Digraph


ModulePath = Tuple[str, ...]
ImportFunctionType = Callable[[str, Dict[str, Any], Dict[str, Any], List[str], int], Any]

class ImportAction:
    UNKNOWN_MODULE_NAME = '<unknown>'
    def __init__(self,
        name: str,
        the_globals: Dict[str, Any],
        fromlist: Optional[List[str]],
        level: int,
        imported_module: ModuleType,
    ) -> None:
        self._name = name
        self._globals = the_globals
        self._fromlist = fromlist
        self._level = level
        self._imported_module = imported_module
    
    def from_name(self) -> str:
        if self._globals is None:
            return self.UNKNOWN_MODULE_NAME
        try:
            return self._globals['__name__']
        except KeyError:
            return self.UNKNOWN_MODULE_NAME
    
    def _build_imported_paths(self) -> Iterable[ModulePath]:
        """Fully qualified names for `from ... import ...` imports

        This resolves relative imports and returns one path for every imported item in the fromlist
        """
        from_module_path = self.from_name().split('.')
        root_module = from_module_path[:-self._level]
        if self._name:
            root_module += self._name.split('.')
        return [tuple(root_module + [from_item]) for from_item in self._fromlist]
    
    def _get_module(self, name: str):
        try:
            return sys.modules[name]
        except KeyError:
            return None

    def _last_module_in_path(self, path: ModulePath) -> ModulePath:
        """Given a path, find the last item that refers to a module object"""
        for sub_path in (path[:-i] for i in range(len(path))):
            if self._get_module('.'.join(sub_path)) is not None:
                return sub_path
        return tuple()

    def imported_names(self) -> Iterable[str]:
        if self._fromlist is None:
            return [self._name]
        imported_paths = self._build_imported_paths()
        imported_module_paths = {self._last_module_in_path(imported_path) for imported_path in imported_paths}
        return ['.'.join(module_path) for module_path in imported_module_paths]


class AbstractImportGraph(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def add_import(self, import_action: ImportAction) -> None:
        pass
    
    @abc.abstractmethod
    def save(self, filename: str) -> None:
        pass
    
    @abc.abstractmethod
    def to_string(self) -> str:
        pass


class DotImportGraph(AbstractImportGraph, Digraph):
    def add_import(self, import_action: ImportAction) -> None:
        for name in import_action.imported_names():
            self.edge(import_action.from_name(), name)
    
    def to_string(self) -> str:
        return self.source
    
    def save(self, filename: str) -> None:
        Digraph.save(self, filename=filename)


class ImportGraphCommand:
    def __init__(self):
        self._arg_parser = argparse.ArgumentParser()
        self._arg_parser.add_argument(
            'module',
            nargs='+',
            help='One or more modules to build an import graph for.',
        )
        self._arg_parser.add_argument(
            '-o', '--output',
            type=argparse.FileType('w'),
            default=None,
        )
        self._import_graph = DotImportGraph()
    
    def _import_wrapper(self, old_import: ImportFunctionType) -> ImportFunctionType:
        def new_import(
            name: str,
            the_globals: Dict[str, Any]=None,
            the_locals: Dict[str, Any]=None,
            fromlist: Tuple[str]=(),
            level: int=0,
        ) -> ModuleType:
            module = old_import(name, the_globals, the_locals, fromlist, level)
            import_action = ImportAction(name, the_globals, fromlist, level, module)
            self._import_graph.add_import(import_action)
            return module
        return new_import

    def run(self, args: List[str]):
        options = self._arg_parser.parse_args(args=args)
        old_import = builtins.__import__
        builtins.__import__ = self._import_wrapper(old_import)
        for module_name in options.module:
            old_import(module_name)
        if options.output is not None:
            self._import_graph.save(options.output.name)
        else:
            print(self._import_graph.to_string(), end='')


def main():
    command = ImportGraphCommand()
    command.run(sys.argv[1:])

if __name__ == '__main__':
    main()
