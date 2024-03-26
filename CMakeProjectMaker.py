import os
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json
from typing import List
import sys
from pathlib import Path


@dataclass_json
@dataclass
class CppConfig:
    target_include_directories: List[str] = field(default_factory=list)
    target_link_libraries: List[str] = field(default_factory=list)
    CMAKE_CXX_STANDARD_REQUIRED: str = field(default="ON")
    CXX_STANDARD: int = field(default=23)


@dataclass_json
@dataclass
class MSVCConfig:
    parent_visual_studio_filter: str = field(default="")
    target_compile_options: str = field(default="/MP")
    VS_PLATFORM_TOOLSET: str = field(default="v143")


@dataclass_json
@dataclass
class ProjectSchema:
    project_name: str= field(default="")
    cpp: CppConfig = field(default_factory=CppConfig)
    MSVC: MSVCConfig = field(default_factory=MSVCConfig)
    source_files: List[str] = field(default_factory=list)
    include_sub_directories: List[str] = field(default_factory=lambda: ['SourceFiles'])
    project_type: str = field(default="EXE")  # or STATIC, or SHARED
    cmake_minimum_required_version: float = field(default=3.14)


@dataclass
class CMakeProjectMaker:
    current_folder: str = field(default=os.getcwd())
    schema: ProjectSchema = field(default_factory=ProjectSchema)

    def _load_item(self, input_schema_file_path: str):
        schema_path = os.path.join(os.path.dirname(__file__), input_schema_file_path)
        with open(schema_path, 'r') as f:
            self.schema = ProjectSchema.from_json(f.read())

    def _cmake_minimum_required(self) -> str:
        text = f"cmake_minimum_required(VERSION {self.schema.cmake_minimum_required_version})\n\n"
        print(text)
        return text

    def _project(self) -> str:
        text = f"project({self.schema.project_name})\n\n"
        print(text)
        return text

    @staticmethod
    def _cmake_files():
        os.mkdir("cmake")
        sub_dir_text = (
            """
MACRO(list_sub_dirs result curdir)
    set(dir_list "")
    file(GLOB_RECURSE all_files CONFIGURE_DEPENDS LIST_DIRECTORIES TRUE  ${curdir}/*.*)
    foreach(dir IN LISTS all_files)
        if (IS_DIRECTORY ${dir})
            # message("${dir}")
            list(APPEND dir_list ${dir})
        endif()
    endforeach()
    set(${result} ${dir_list})
ENDMACRO()
            """
        )
        with open("cmake/ListSubDirs.cmake", 'w') as file:
            file.write(sub_dir_text)

        source_files_text = (
            """
include(${CMAKE_CURRENT_SOURCE_DIR}//cmake/ListSubDirs.cmake)

file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS
    ${CMAKE_CURRENT_SOURCE_DIR}/*.cpp
)

file(GLOB_RECURSE HEADERS CONFIGURE_DEPENDS 
    ${CMAKE_CURRENT_SOURCE_DIR}/*.h
    ${CMAKE_CURRENT_SOURCE_DIR}/*.hpp
)

list_sub_dirs(SELF_INCLUDE_SOURCE_DIRECTORIES ${CMAKE_CURRENT_SOURCE_DIR})
list(APPEND SELF_INCLUDE_SOURCE_DIRECTORIES ${CMAKE_CURRENT_SOURCE_DIR})

list(FILTER SELF_INCLUDE_SOURCE_DIRECTORIES EXCLUDE REGEX "cmake")

source_group(TREE ${CMAKE_CURRENT_SOURCE_DIR} PREFIX "" FILES ${SOURCES} ${HEADERS})
            """
        )
        with open("cmake/SourceFiles.cmake", 'w') as file:
            file.write(source_files_text)

    def _project_type(self) -> str:
        lib_type = ""
        if self.schema.project_type == "EXE":
            command = "add_executable"
            with open("main.cpp", 'w') as file:
                text = (
                    """
 #include <iostream>

using namespace std;

int main(){

    cout << "hellow world" << endl;
    return 0;
}
                    """
                )
                file.write(text)
        else:
            command = "add_library"
            lib_type = f"{self.schema.project_type}"

        text = f"{command}(${{PROJECT_NAME}} {lib_type} ${{SOURCES}} ${{HEADERS}})\n\n"

        print(text)
        return text

    def _cpp_standards_flags(self) -> str:
        text = (
            f"set(CMAKE_CXX_STANDARD_REQUIRED {self.schema.cpp.CMAKE_CXX_STANDARD_REQUIRED})\n"
            f"set_property(TARGET ${{PROJECT_NAME}} PROPERTY CXX_STANDARD "
            f"{self.schema.cpp.CXX_STANDARD})\n\n"
        )
        print(text)
        return text

    def _msvc_flags(self) -> str:
        parent_folder = ""
        if self.schema.MSVC.parent_visual_studio_filter != "":
            parent_folder = f"set_target_properties(${{PROJECT_NAME}} PROPERTIES FOLDER" \
                        f" \"{self.schema.MSVC.parent_visual_studio_filter}\")\n"
        res = (
            f"if(MSVC)\n"
            f"  {parent_folder}\n"
            f"  set_target_properties(${{PROJECT_NAME}} PROPERTIES VS_PLATFORM_TOOLSET"
            f" \"{self.schema.MSVC.VS_PLATFORM_TOOLSET}\")\n"
            f"  target_compile_options(${{PROJECT_NAME}} PRIVATE \"{self.schema.MSVC.target_compile_options}\")\n"
            f"endif()\n\n"
        )
        print(res)
        return res

    def _additional_include_directories(self) -> str:
        header = f"target_include_directories(${{PROJECT_NAME}} PUBLIC\n"
        text = header + "\n".join(self.schema.cpp.target_include_directories) + "\n)\n\n"
        print(text)
        return text

    def _link_libraries(self) -> str:
        header = f"target_link_libraries(${{PROJECT_NAME}} PUBLIC\n"
        text = header + "\n".join(self.schema.cpp.target_link_libraries) + "\n)\n\n"
        print(text)
        return text

    def _include_sub_directories(self) -> str:
        text = "" + \
               "\n".join(f"include(${{CMAKE_CURRENT_SOURCE_DIR}}/cmake/{item}.cmake)"
                         for item in self.schema.include_sub_directories) \
               + "\n\n"
        print(text)
        return text

    def _source_files(self):
        os.mkdir("source")

        for file_name in self.schema.source_files:
            with open(f"source/{file_name}.hpp", 'w') as file:
                file.write("#pragma once\n")
            with open(f"source/{file_name}.cpp", 'w') as file:
                file.write(f"#include \"{file_name}.hpp\"\n")

    def _create_project_folder_and_navigate(self):
        folder_path = Path(self.schema.project_name)
        folder_path.mkdir(parents=True, exist_ok=True)
        os.chdir(folder_path)

    def _call_cmake(self):
        import subprocess

        # Define your source and build directories
        source_dir = self.current_folder + f"/{self.schema.project_name}"
        build_dir = self.current_folder + f"/{self.schema.project_name}/../build"

        # Specify the generator and any other options or variables
        generator = "Visual Studio 17 2022"
        # Example of defining a CMake variable: CMAKE_INSTALL_PREFIX
        cmake_install_prefix = f"C:/Program Files/{self.schema.project_name}"

        # Construct the CMake command
        cmake_command = [
            "cmake",
            "-S", source_dir,
            "-B", build_dir,
            "-G", generator,
            "-DCMAKE_INSTALL_PREFIX=" + cmake_install_prefix
        ]

        # Run the CMake command
        subprocess.run(cmake_command, check=True)

    def create_project(self, input_schema_file_path: str):
        file_text = ""
        self._load_item(input_schema_file_path)
        self._create_project_folder_and_navigate()
        file_text += self._cmake_minimum_required()
        self._cmake_files()
        self._source_files()
        file_text += self._project()
        file_text += self._include_sub_directories()
        file_text += self._project_type()
        if self.schema.cpp:
            file_text += self._cpp_standards_flags()
            if len(self.schema.cpp.target_include_directories) > 0:
                file_text += self._additional_include_directories()
            if len(self.schema.cpp.target_link_libraries) > 0:
                file_text += self._link_libraries()
        if self.schema.MSVC:
            file_text += self._msvc_flags()

        with open("CMakeLists.txt", 'w') as file:
            file.write(file_text)

        self._call_cmake()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("please provide json schema for project")
        exit()
    if not os.path.isfile(sys.argv[1]):
        print("file does not exists!")
        exit()

    project_creator = CMakeProjectMaker()
    project_creator.create_project(input_schema_file_path=sys.argv[1])
