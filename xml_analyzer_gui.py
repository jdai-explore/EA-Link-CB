import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import xml.etree.ElementTree as ET
from collections import defaultdict, Counter
import os
import json
import threading
import base64
from datetime import datetime
import re

class EAXMLAnalyzer:
    def __init__(self):
        self.reset()
    
    def reset(self):
        # Core EA structures
        self.packages = {}
        self.elements = {}
        self.diagrams = {}
        self.connectors = {}
        self.tagged_values = defaultdict(list)
        self.stereotypes = {}
        
        # Documentation metadata
        self.model_info = {}
        self.authors = set()
        self.versions = set()
        
        # Analysis stats
        self.stats = {
            'total_packages': 0,
            'total_elements': 0,
            'total_diagrams': 0,
            'total_connectors': 0,
            'element_types': Counter(),
            'diagram_types': Counter(),
            'connector_types': Counter()
        }
    
    def analyze_file(self, xml_file_path):
        """Analyze EA XML file and extract model structure"""
        self.reset()
        
        # Handle different encodings
        content = self._read_file_with_encoding(xml_file_path)
        
        # Parse XML with robust error handling
        try:
            # First try parsing the file directly
            tree = ET.parse(xml_file_path)
            root = tree.getroot()
        except ET.ParseError as e:
            try:
                # If that fails, try parsing the content string
                root = ET.fromstring(content)
            except ET.ParseError:
                # If both fail, try cleaning the content
                try:
                    # Remove problematic namespace declarations
                    cleaned_content = self._clean_xml_content(content)
                    root = ET.fromstring(cleaned_content)
                except ET.ParseError:
                    raise ValueError(f"Invalid XML format: {e}")
        
        # Extract EA model structure with error handling
        try:
            self._extract_model_info(root)
        except Exception as e:
            print(f"Warning: Could not extract model info: {e}")
        
        try:
            self._extract_packages(root)
        except Exception as e:
            print(f"Warning: Could not extract packages: {e}")
        
        try:
            self._extract_elements(root)
        except Exception as e:
            print(f"Warning: Could not extract elements: {e}")
        
        try:
            self._extract_diagrams(root)
        except Exception as e:
            print(f"Warning: Could not extract diagrams: {e}")
        
        try:
            self._extract_connectors(root)
        except Exception as e:
            print(f"Warning: Could not extract connectors: {e}")
        
        try:
            self._extract_tagged_values(root)
        except Exception as e:
            print(f"Warning: Could not extract tagged values: {e}")
        
        # Calculate statistics
        self._calculate_stats()
        
        return {
            'file_name': os.path.basename(xml_file_path),
            'file_size': len(content.encode('utf-8')),
            'model_info': self.model_info,
            'stats': self.stats,
            'packages': self.packages,
            'elements': self.elements,
            'diagrams': self.diagrams,
            'connectors': self.connectors,
            'tagged_values': dict(self.tagged_values),
            'authors': list(self.authors),
            'versions': list(self.versions)
        }
    
    def _clean_xml_content(self, content):
        """Clean XML content to remove problematic namespace declarations"""
        # Remove problematic namespace prefixes that might not be properly declared
        import re
        
        # Replace undefined namespace prefixes with simple element names
        problematic_prefixes = ['xml:', 'xmlns:', 'xsi:', 'uml:', 'xmi:']
        
        cleaned = content
        for prefix in problematic_prefixes:
            # Replace prefixed attributes and elements
            cleaned = re.sub(f'{prefix}([a-zA-Z][a-zA-Z0-9]*)', r'\1', cleaned)
        
        return cleaned
    
    def _read_file_with_encoding(self, file_path):
        """Read file with multiple encoding attempts"""
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1', 'utf-16']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        
        # Fallback: read as binary and decode with error handling
        with open(file_path, 'rb') as f:
            raw_content = f.read()
            return raw_content.decode('utf-8', errors='ignore')
    
    def _extract_model_info(self, root):
        """Extract model metadata and information with robust error handling"""
        try:
            # Simple approach - avoid namespace operations that might fail
            
            # Look for model elements without using namespaces first
            model_candidates = []
            
            # Search for common EA model elements
            for elem in root.iter():
                tag_name = elem.tag.split('}')[-1].lower()  # Remove namespace, get local name
                if tag_name in ['model', 'documentation']:
                    model_candidates.append(elem)
            
            # Extract info from found elements
            for elem in model_candidates:
                tag_name = elem.tag.split('}')[-1].lower()
                
                if tag_name == 'documentation' and elem.text:
                    self.model_info['documentation'] = elem.text
                elif tag_name == 'model':
                    # Extract model attributes using various possible attribute names
                    self.model_info['name'] = (elem.get('name') or elem.get('Name') or 
                                             elem.get('xmi.name') or 'Unnamed Model')
                    self.model_info['id'] = (elem.get('xmi.id') or elem.get('id') or 
                                           elem.get('Id'))
                    self.model_info['type'] = (elem.get('Type') or elem.get('type') or 
                                             'UML Model')
                    self.model_info['created'] = elem.get('Created') or elem.get('created')
                    self.model_info['modified'] = elem.get('Modified') or elem.get('modified')
                    break
            
            # If no model info found, use root element info
            if not self.model_info.get('name'):
                self.model_info['name'] = (root.get('name') or root.get('Name') or 
                                         'Extracted Model')
                self.model_info['type'] = f"XML Root: {root.tag.split('}')[-1]}"
                
        except Exception as e:
            print(f"Error extracting model info: {e}")
            self.model_info['name'] = 'Unknown Model'
            self.model_info['type'] = 'Unknown'
    
    def _extract_packages(self, root):
        """Extract package hierarchy and information with robust error handling"""
        try:
            # Simple approach - iterate through all elements and find packages
            package_candidates = []
            
            for elem in root.iter():
                tag_name = elem.tag.split('}')[-1].lower()  # Remove namespace
                
                # Look for elements that are likely packages
                if tag_name in ['package', 'packages']:
                    package_candidates.append(elem)
                # Also check if element has package-like attributes
                elif elem.get('Name') and elem.get('PackageID'):
                    package_candidates.append(elem)
            
            for pkg in package_candidates:
                pkg_info = {
                    'id': (pkg.get('Id') or pkg.get('id') or pkg.get('xmi.id') or 
                           str(id(pkg))),
                    'name': (pkg.get('Name') or pkg.get('name') or 'Unnamed Package'),
                    'parent_id': (pkg.get('ParentID') or pkg.get('parent') or 
                                 pkg.get('owner')),
                    'stereotype': pkg.get('Stereotype') or pkg.get('stereotype'),
                    'notes': self._extract_notes(pkg),
                    'created': pkg.get('Created') or pkg.get('created'),
                    'modified': pkg.get('Modified') or pkg.get('modified'),
                    'author': pkg.get('Author') or pkg.get('author'),
                    'version': pkg.get('Version') or pkg.get('version'),
                    'elements': [],
                    'sub_packages': []
                }
                
                # Track authors and versions
                if pkg_info['author']:
                    self.authors.add(pkg_info['author'])
                if pkg_info['version']:
                    self.versions.add(pkg_info['version'])
                
                self.packages[pkg_info['id']] = pkg_info
                self.stats['total_packages'] += 1
                
        except Exception as e:
            print(f"Error extracting packages: {e}")
    
    def _extract_elements(self, root):
        """Extract model elements with robust error handling"""
        try:
            # Simple approach - iterate through all elements
            element_candidates = []
            
            for elem in root.iter():
                tag_name = elem.tag.split('}')[-1].lower()
                
                # Look for elements that are likely model elements
                if tag_name in ['element', 'class', 'component', 'actor', 'usecase', 
                               'interface', 'object', 'node', 'artifact']:
                    element_candidates.append(elem)
                # Also check if element has model element attributes
                elif (elem.get('Name') and elem.get('Type') and 
                      elem.get('Type') in ['Class', 'Component', 'Actor', 'UseCase', 
                                          'Interface', 'Object', 'Node', 'Artifact']):
                    element_candidates.append(elem)
            
            for elem in element_candidates:
                elem_info = {
                    'id': (elem.get('Id') or elem.get('id') or elem.get('xmi.id') or 
                           str(id(elem))),
                    'name': (elem.get('Name') or elem.get('name') or 'Unnamed Element'),
                    'type': (elem.get('Type') or elem.get('type') or 
                            elem.tag.split('}')[-1]),
                    'package_id': (elem.get('PackageID') or elem.get('package') or 
                                  elem.get('owner')),
                    'stereotype': elem.get('Stereotype') or elem.get('stereotype'),
                    'notes': self._extract_notes(elem),
                    'abstract': (elem.get('Abstract') == 'true' or 
                               elem.get('isAbstract') == 'true'),
                    'visibility': (elem.get('Visibility') or elem.get('visibility')),
                    'created': elem.get('Created') or elem.get('created'),
                    'modified': elem.get('Modified') or elem.get('modified'),
                    'author': elem.get('Author') or elem.get('author'),
                    'version': elem.get('Version') or elem.get('version'),
                    'complexity': elem.get('Complexity'),
                    'status': elem.get('Status') or elem.get('status'),
                    'attributes': [],
                    'operations': [],
                    'tagged_values': []
                }
                
                # Extract attributes and operations
                try:
                    self._extract_attributes(elem, elem_info)
                    self._extract_operations(elem, elem_info)
                except Exception as e:
                    print(f"Error extracting attributes/operations for {elem_info['name']}: {e}")
                
                # Track statistics
                self.stats['element_types'][elem_info['type']] += 1
                if elem_info['author']:
                    self.authors.add(elem_info['author'])
                if elem_info['version']:
                    self.versions.add(elem_info['version'])
                
                self.elements[elem_info['id']] = elem_info
                self.stats['total_elements'] += 1
                
        except Exception as e:
            print(f"Error extracting elements: {e}")
    
    def _extract_attributes(self, element, elem_info):
        """Extract attributes for an element"""
        attrs = element.findall('.//Attributes/Attribute') + element.findall('.//Attribute')
        
        for attr in attrs:
            attr_info = {
                'id': attr.get('Id') or attr.get('id'),
                'name': attr.get('Name') or attr.get('name', 'unnamed'),
                'type': attr.get('Type') or attr.get('type'),
                'visibility': attr.get('Visibility') or attr.get('visibility'),
                'static': attr.get('Static') == 'true',
                'default': attr.get('Default'),
                'notes': self._extract_notes(attr),
                'stereotype': attr.get('Stereotype')
            }
            elem_info['attributes'].append(attr_info)
    
    def _extract_operations(self, element, elem_info):
        """Extract operations/methods for an element"""
        ops = element.findall('.//Operations/Operation') + element.findall('.//Operation')
        
        for op in ops:
            op_info = {
                'id': op.get('Id') or op.get('id'),
                'name': op.get('Name') or op.get('name', 'unnamed'),
                'type': op.get('Type') or op.get('type'),
                'visibility': op.get('Visibility') or op.get('visibility'),
                'static': op.get('Static') == 'true',
                'abstract': op.get('Abstract') == 'true',
                'notes': self._extract_notes(op),
                'stereotype': op.get('Stereotype'),
                'parameters': []
            }
            
            # Extract parameters
            params = op.findall('.//Parameters/Parameter') + op.findall('.//Parameter')
            for param in params:
                param_info = {
                    'name': param.get('Name') or param.get('name'),
                    'type': param.get('Type') or param.get('type'),
                    'kind': param.get('Kind'),
                    'default': param.get('Default')
                }
                op_info['parameters'].append(param_info)
            
            elem_info['operations'].append(op_info)
    
    def _extract_diagrams(self, root):
        """Extract diagram information and embedded content"""
        # Use discovered namespaces
        namespaces = getattr(self, 'namespaces_map', {})
        
        # Look for diagrams in various EA XML structures
        diagram_candidates = []
        
        # EA-specific diagram locations
        diagram_candidates.extend(root.findall('.//Diagrams/Diagram'))
        diagram_candidates.extend(root.findall('.//Diagram'))
        
        # UML diagram locations
        if 'uml' in namespaces:
            try:
                diagram_candidates.extend(root.findall('.//uml:Diagram', namespaces))
            except:
                pass
        
        # XMI diagram locations
        diagram_candidates.extend(root.findall('.//diagrams/diagram'))
        diagram_candidates.extend(root.findall('.//xmi:Extension//diagrams'))
        
        # EA Project file diagram references
        diagram_candidates.extend(root.findall('.//t_diagram'))
        diagram_candidates.extend(root.findall('.//EAP//diagrams//diagram'))
        
        # Remove duplicates
        seen = set()
        unique_diagrams = []
        for diag in diagram_candidates:
            diag_id = id(diag)
            if diag_id not in seen:
                seen.add(diag_id)
                unique_diagrams.append(diag)
        
        print(f"Found {len(unique_diagrams)} potential diagram elements")  # Debug output
        
        for diag in unique_diagrams:
            diag_info = {
                'id': (diag.get('Id') or diag.get('xmi.id') or diag.get('id') or 
                       diag.get('diagramId') or str(id(diag))),
                'name': (diag.get('Name') or diag.get('name') or 
                        diag.get('xmi:name') or 'Unnamed Diagram'),
                'type': (diag.get('Type') or diag.get('type') or 
                        diag.get('DiagramType') or 'Unknown'),
                'package_id': (diag.get('PackageID') or diag.get('package') or 
                              diag.get('owner')),
                'author': diag.get('Author') or diag.get('author'),
                'created': diag.get('Created') or diag.get('created'),
                'modified': diag.get('Modified') or diag.get('modified'),
                'version': diag.get('Version') or diag.get('version'),
                'notes': self._extract_notes(diag),
                'elements': [],
                'has_image': False,
                'image_data': None,
                'image_format': None,
                'style_ex': diag.get('StyleEx'),  # EA styling information
                'swim_lanes': diag.get('SwimLanes'),
                'scale': diag.get('Scale')
            }
            
            # Extract diagram elements/objects
            self._extract_diagram_elements(diag, diag_info)
            
            # Look for embedded diagram images with enhanced detection
            self._extract_diagram_image_enhanced(diag, diag_info)
            
            # Track statistics
            self.stats['diagram_types'][diag_info['type']] += 1
            if diag_info['author']:
                self.authors.add(diag_info['author'])
            if diag_info['version']:
                self.versions.add(diag_info['version'])
            
            self.diagrams[diag_info['id']] = diag_info
            self.stats['total_diagrams'] += 1
            
            print(f"Processed diagram: {diag_info['name']} (Type: {diag_info['type']}, Has Image: {diag_info['has_image']})")
    
    def _extract_diagram_elements(self, diagram_elem, diag_info):
        """Extract elements that appear in the diagram"""
        # Look for diagram elements in various formats
        element_sources = [
            diagram_elem.findall('.//DiagramElements/DiagramElement'),
            diagram_elem.findall('.//DiagramElement'),
            diagram_elem.findall('.//elements/element'),
            diagram_elem.findall('.//diagramElement'),
            diagram_elem.findall('.//DiagramObjects/DiagramObject'),
            diagram_elem.findall('.//DiagramObject')
        ]
        
        for elements in element_sources:
            for diag_elem in elements:
                diag_elem_info = {
                    'element_id': (diag_elem.get('ElementID') or diag_elem.get('element') or 
                                  diag_elem.get('Object_ID') or diag_elem.get('objectId')),
                    'geometry': diag_elem.get('Geometry') or diag_elem.get('geometry'),
                    'style': diag_elem.get('Style') or diag_elem.get('style'),
                    'left': diag_elem.get('left'),
                    'top': diag_elem.get('top'),
                    'right': diag_elem.get('right'),
                    'bottom': diag_elem.get('bottom'),
                    'sequence': diag_elem.get('Sequence')
                }
                diag_info['elements'].append(diag_elem_info)
    
    def _extract_diagram_image_enhanced(self, diagram_elem, diag_info):
        """Enhanced diagram image extraction with multiple format support"""
        # Look for different image storage formats in EA
        image_sources = [
            # EA standard image locations
            diagram_elem.find('.//Image'),
            diagram_elem.find('.//MetaFile'),
            diagram_elem.find('.//DiagramImage'),
            diagram_elem.find('.//Metafile'),
            
            # XMI extension image locations
            diagram_elem.find('.//xmi:Extension//image'),
            diagram_elem.find('.//image'),
            diagram_elem.find('.//png'),
            diagram_elem.find('.//jpg'),
            diagram_elem.find('.//bmp'),
            
            # EA project file image references
            diagram_elem.find('.//PDATA1'),
            diagram_elem.find('.//PDATA2'),
            diagram_elem.find('.//PDATA3'),
            diagram_elem.find('.//StyleEx'),
        ]
        
        for img_elem in image_sources:
            if img_elem is not None:
                image_text = img_elem.text or img_elem.get('data') or img_elem.get('content')
                
                if image_text and image_text.strip():
                    try:
                        # Check if it's base64 encoded
                        if self._is_base64(image_text.strip()):
                            diag_info['has_image'] = True
                            diag_info['image_data'] = image_text.strip()
                            diag_info['image_format'] = self._detect_image_format(img_elem.tag)
                            print(f"Found base64 image in {img_elem.tag} for diagram {diag_info['name']}")
                            break
                        # Check if it's metafile data (EA specific)
                        elif len(image_text.strip()) > 100 and any(c in image_text for c in ['EMF', 'WMF']):
                            diag_info['has_image'] = True
                            diag_info['image_data'] = image_text.strip()
                            diag_info['image_format'] = 'metafile'
                            print(f"Found metafile data in {img_elem.tag} for diagram {diag_info['name']}")
                            break
                        # Check for other binary data indicators
                        elif len(image_text.strip()) > 50:
                            diag_info['has_image'] = True
                            diag_info['image_data'] = image_text.strip()
                            diag_info['image_format'] = 'unknown'
                            print(f"Found potential image data in {img_elem.tag} for diagram {diag_info['name']}")
                            break
                    except Exception as e:
                        print(f"Error processing image data: {e}")
                        pass
        
        # Also check if there are any image file references
        image_refs = [
            diagram_elem.get('ImageFile'),
            diagram_elem.get('imageFile'),
            diagram_elem.get('ImagePath'),
            diagram_elem.get('imagePath')
        ]
        
        for ref in image_refs:
            if ref:
                diag_info['has_image'] = True
                diag_info['image_data'] = ref
                diag_info['image_format'] = 'file_reference'
                print(f"Found image file reference: {ref}")
                break
    
    def _is_base64(self, s):
        """Check if string is valid base64"""
        try:
            if len(s) < 4:
                return False
            # Check if it has base64 characteristics
            import string
            base64_chars = string.ascii_letters + string.digits + '+/='
            if not all(c in base64_chars for c in s):
                return False
            # Try to decode
            import base64
            base64.b64decode(s, validate=True)
            return True
        except:
            return False
    
    def _detect_image_format(self, tag_name):
        """Detect image format from tag name or content"""
        tag_lower = tag_name.lower()
        if 'png' in tag_lower:
            return 'png'
        elif 'jpg' in tag_lower or 'jpeg' in tag_lower:
            return 'jpeg'
        elif 'bmp' in tag_lower:
            return 'bmp'
        elif 'metafile' in tag_lower or 'emf' in tag_lower or 'wmf' in tag_lower:
            return 'metafile'
        elif 'image' in tag_lower:
            return 'image'
        else:
            return 'unknown'
    
    def _extract_connectors(self, root):
        """Extract relationships/connectors between elements"""
        connectors = (
            root.findall('.//Connectors/Connector') +
            root.findall('.//Connector')
        )
        
        for conn in connectors:
            conn_info = {
                'id': conn.get('Id') or conn.get('id'),
                'name': conn.get('Name') or conn.get('name'),
                'type': conn.get('Type') or conn.get('type'),
                'source_id': conn.get('SourceID') or conn.get('source'),
                'target_id': conn.get('TargetID') or conn.get('target'),
                'direction': conn.get('Direction'),
                'stereotype': conn.get('Stereotype'),
                'notes': self._extract_notes(conn),
                'source_role': None,
                'target_role': None
            }
            
            # Extract role information
            source_role = conn.find('.//SourceRole') or conn.find('.//Source')
            if source_role is not None:
                conn_info['source_role'] = {
                    'name': source_role.get('Name') or source_role.get('name'),
                    'multiplicity': source_role.get('Multiplicity'),
                    'visibility': source_role.get('Visibility')
                }
            
            target_role = conn.find('.//TargetRole') or conn.find('.//Target')
            if target_role is not None:
                conn_info['target_role'] = {
                    'name': target_role.get('Name') or target_role.get('name'),
                    'multiplicity': target_role.get('Multiplicity'),
                    'visibility': target_role.get('Visibility')
                }
            
            # Track statistics
            self.stats['connector_types'][conn_info['type']] += 1
            
            self.connectors[conn_info['id']] = conn_info
            self.stats['total_connectors'] += 1
    
    def _extract_tagged_values(self, root):
        """Extract tagged values (custom properties)"""
        tagged_values = (
            root.findall('.//TaggedValues/TaggedValue') +
            root.findall('.//TaggedValue')
        )
        
        for tv in tagged_values:
            element_id = tv.get('ElementID') or tv.get('element')
            tag_info = {
                'name': tv.get('Name') or tv.get('name'),
                'value': tv.get('Value') or tv.get('value') or tv.text,
                'notes': self._extract_notes(tv)
            }
            
            if element_id:
                self.tagged_values[element_id].append(tag_info)
    
    def _extract_notes(self, element):
        """Extract notes/documentation from an element"""
        notes_elem = element.find('.//Notes') or element.find('.//Documentation')
        if notes_elem is not None:
            return notes_elem.text or ''
        return element.get('Notes', '')
    
    def _calculate_stats(self):
        """Calculate final statistics"""
        # Build package hierarchy
        for pkg_id, pkg in self.packages.items():
            if pkg['parent_id'] and pkg['parent_id'] in self.packages:
                self.packages[pkg['parent_id']]['sub_packages'].append(pkg_id)
        
        # Link elements to packages
        for elem_id, elem in self.elements.items():
            if elem['package_id'] and elem['package_id'] in self.packages:
                self.packages[elem['package_id']]['elements'].append(elem_id)
        
        # Add tagged values to elements
        for elem_id, elem in self.elements.items():
            if elem_id in self.tagged_values:
                elem['tagged_values'] = self.tagged_values[elem_id]


class EAAnalyzerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Enterprise Architect XML Analyzer")
        self.root.geometry("1200x800")
        
        self.analysis_results = None
        self.current_file = None
        
        self.create_widgets()
        self.create_menu()
    
    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open EA XML File", command=self.open_file)
        file_menu.add_separator()
        file_menu.add_command(label="Export Analysis to JSON", command=self.export_json)
        file_menu.add_command(label="Generate Word Document", command=self.generate_word_doc)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Package Hierarchy", command=self.show_package_hierarchy)
        tools_menu.add_command(label="Element Relationships", command=self.show_relationships)
        tools_menu.add_command(label="Diagram Overview", command=self.show_diagrams)
        tools_menu.add_separator()
        tools_menu.add_command(label="Debug XML Structure", command=self.debug_xml_structure)
        tools_menu.add_command(label="Search XML Content", command=self.search_xml_content)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # File selection
        file_frame = ttk.LabelFrame(main_frame, text="EA XML File Selection", padding="10")
        file_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        file_frame.columnconfigure(1, weight=1)
        
        ttk.Button(file_frame, text="Select EA XML File", command=self.open_file).grid(row=0, column=0, padx=(0, 10))
        self.file_label = ttk.Label(file_frame, text="No file selected", foreground="gray")
        self.file_label.grid(row=0, column=1, sticky=(tk.W, tk.E))
        
        # Analysis button
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, pady=(0, 10))
        
        self.analyze_btn = ttk.Button(button_frame, text="Analyze EA Model", 
                                     command=self.start_analysis, state=tk.DISABLED)
        self.analyze_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.generate_btn = ttk.Button(button_frame, text="Generate Word Document", 
                                      command=self.generate_word_doc, state=tk.DISABLED)
        self.generate_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.status_label = ttk.Label(button_frame, text="Ready")
        self.status_label.pack(side=tk.LEFT)
        
        # Results notebook
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.create_overview_tab()
        self.create_packages_tab()
        self.create_elements_tab()
        self.create_diagrams_tab()
        self.create_relationships_tab()
    
    def create_overview_tab(self):
        overview_frame = ttk.Frame(self.notebook)
        self.notebook.add(overview_frame, text="Model Overview")
        
        overview_frame.columnconfigure(0, weight=1)
        overview_frame.rowconfigure(0, weight=1)
        
        self.overview_text = scrolledtext.ScrolledText(overview_frame, height=20)
        self.overview_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
    def create_packages_tab(self):
        packages_frame = ttk.Frame(self.notebook)
        self.notebook.add(packages_frame, text="Packages")
        
        packages_frame.columnconfigure(0, weight=1)
        packages_frame.rowconfigure(0, weight=1)
        
        columns = ('Name', 'Type', 'Elements', 'Sub-Packages', 'Author', 'Version', 'Modified')
        self.packages_tree = ttk.Treeview(packages_frame, columns=columns, show='headings')
        
        for col in columns:
            self.packages_tree.heading(col, text=col)
            self.packages_tree.column(col, width=100)
        
        scrollbar_pkg = ttk.Scrollbar(packages_frame, orient=tk.VERTICAL, command=self.packages_tree.yview)
        self.packages_tree.configure(yscrollcommand=scrollbar_pkg.set)
        
        self.packages_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar_pkg.grid(row=0, column=1, sticky=(tk.N, tk.S))
    
    def create_elements_tab(self):
        elements_frame = ttk.Frame(self.notebook)
        self.notebook.add(elements_frame, text="Elements")
        
        elements_frame.columnconfigure(0, weight=1)
        elements_frame.rowconfigure(0, weight=1)
        
        columns = ('Name', 'Type', 'Package', 'Stereotype', 'Attributes', 'Operations', 'Author')
        self.elements_tree = ttk.Treeview(elements_frame, columns=columns, show='headings')
        
        for col in columns:
            self.elements_tree.heading(col, text=col)
            self.elements_tree.column(col, width=120)
        
        scrollbar_elem = ttk.Scrollbar(elements_frame, orient=tk.VERTICAL, command=self.elements_tree.yview)
        self.elements_tree.configure(yscrollcommand=scrollbar_elem.set)
        
        self.elements_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar_elem.grid(row=0, column=1, sticky=(tk.N, tk.S))
    
    def create_diagrams_tab(self):
        diagrams_frame = ttk.Frame(self.notebook)
        self.notebook.add(diagrams_frame, text="Diagrams")
        
        diagrams_frame.columnconfigure(0, weight=1)
        diagrams_frame.rowconfigure(0, weight=1)
        
        columns = ('Name', 'Type', 'Package', 'Elements', 'Has Image', 'Author', 'Modified')
        self.diagrams_tree = ttk.Treeview(diagrams_frame, columns=columns, show='headings')
        
        for col in columns:
            self.diagrams_tree.heading(col, text=col)
            self.diagrams_tree.column(col, width=120)
        
        scrollbar_diag = ttk.Scrollbar(diagrams_frame, orient=tk.VERTICAL, command=self.diagrams_tree.yview)
        self.diagrams_tree.configure(yscrollcommand=scrollbar_diag.set)
        
        self.diagrams_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar_diag.grid(row=0, column=1, sticky=(tk.N, tk.S))
    
    def create_relationships_tab(self):
        relationships_frame = ttk.Frame(self.notebook)
        self.notebook.add(relationships_frame, text="Relationships")
        
        relationships_frame.columnconfigure(0, weight=1)
        relationships_frame.rowconfigure(0, weight=1)
        
        columns = ('Name', 'Type', 'Source', 'Target', 'Direction', 'Stereotype')
        self.relationships_tree = ttk.Treeview(relationships_frame, columns=columns, show='headings')
        
        for col in columns:
            self.relationships_tree.heading(col, text=col)
            self.relationships_tree.column(col, width=120)
        
        scrollbar_rel = ttk.Scrollbar(relationships_frame, orient=tk.VERTICAL, command=self.relationships_tree.yview)
        self.relationships_tree.configure(yscrollcommand=scrollbar_rel.set)
        
        self.relationships_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar_rel.grid(row=0, column=1, sticky=(tk.N, tk.S))
    
    def open_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Enterprise Architect XML File",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
        )
        
        if file_path:
            self.current_file = file_path
            self.file_label.config(text=os.path.basename(file_path), foreground="black")
            self.analyze_btn.config(state=tk.NORMAL)
            self.clear_results()
    
    def start_analysis(self):
        if not self.current_file:
            messagebox.showerror("Error", "Please select an EA XML file first.")
            return
        
        self.analyze_btn.config(state=tk.DISABLED)
        self.status_label.config(text="Analyzing EA model...")
        
        thread = threading.Thread(target=self.analyze_xml)
        thread.daemon = True
        thread.start()
    
    def analyze_xml(self):
        try:
            analyzer = EAXMLAnalyzer()
            self.analysis_results = analyzer.analyze_file(self.current_file)
            self.root.after(0, self.analysis_complete)
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda: self.analysis_error(error_msg))
    
    def analysis_complete(self):
        self.status_label.config(text="Analysis complete!")
        self.analyze_btn.config(state=tk.NORMAL)
        self.generate_btn.config(state=tk.NORMAL)
        self.populate_results()
        messagebox.showinfo("Success", "EA model analysis completed successfully!")
    
    def analysis_error(self, error_msg):
        self.status_label.config(text="Analysis failed!")
        self.analyze_btn.config(state=tk.NORMAL)
        messagebox.showerror("Analysis Error", f"Failed to analyze EA XML file:\n\n{error_msg}")
    
    def populate_results(self):
        if not self.analysis_results:
            return
        
        self.populate_overview()
        self.populate_packages()
        self.populate_elements()
        self.populate_diagrams()
        self.populate_relationships()
    
    def populate_overview(self):
        results = self.analysis_results
        model_info = results['model_info']
        stats = results['stats']
        
        overview_text = f"""ENTERPRISE ARCHITECT MODEL ANALYSIS
{'='*60}

Model Information:
  Name: {model_info.get('name', 'Unknown')}
  Type: {model_info.get('type', 'Unknown')}
  Created: {model_info.get('created', 'Unknown')}
  Modified: {model_info.get('modified', 'Unknown')}

File Information:
  File: {results['file_name']}
  Size: {results['file_size']:,} bytes

MODEL STATISTICS:
{'='*30}
  Packages: {stats['total_packages']:,}
  Elements: {stats['total_elements']:,}
  Diagrams: {stats['total_diagrams']:,}
  Relationships: {stats['total_connectors']:,}

ELEMENT TYPES:
{'='*15}
"""
        
        for elem_type, count in stats['element_types'].most_common(10):
            overview_text += f"  {elem_type}: {count:,}\n"
        
        overview_text += f"\nDIAGRAM TYPES:\n{'='*15}\n"
        for diag_type, count in stats['diagram_types'].most_common(10):
            overview_text += f"  {diag_type}: {count:,}\n"
        
        overview_text += f"\nRELATIONSHIP TYPES:\n{'='*18}\n"
        for conn_type, count in stats['connector_types'].most_common(10):
            overview_text += f"  {conn_type}: {count:,}\n"
        
        overview_text += f"\nAUTHORS:\n{'='*8}\n"
        for author in sorted(results['authors'])[:10]:
            overview_text += f"  {author}\n"
        
        overview_text += f"\nVERSIONS:\n{'='*9}\n"
        for version in sorted(results['versions'])[:10]:
            overview_text += f"  {version}\n"
        
        self.overview_text.delete(1.0, tk.END)
        self.overview_text.insert(tk.END, overview_text)
    
    def populate_packages(self):
        for item in self.packages_tree.get_children():
            self.packages_tree.delete(item)
        
        if not self.analysis_results:
            return
        
        packages = self.analysis_results['packages']
        
        for pkg_id, pkg in packages.items():
            self.packages_tree.insert('', tk.END, values=(
                pkg['name'],
                pkg.get('stereotype', ''),
                len(pkg['elements']),
                len(pkg['sub_packages']),
                pkg.get('author', ''),
                pkg.get('version', ''),
                pkg.get('modified', '')
            ))
    
    def populate_elements(self):
        for item in self.elements_tree.get_children():
            self.elements_tree.delete(item)
        
        if not self.analysis_results:
            return
        
        elements = self.analysis_results['elements']
        packages = self.analysis_results['packages']
        
        for elem_id, elem in elements.items():
            package_name = ''
            if elem['package_id'] and elem['package_id'] in packages:
                package_name = packages[elem['package_id']]['name']
            
            self.elements_tree.insert('', tk.END, values=(
                elem['name'],
                elem['type'],
                package_name,
                elem.get('stereotype', ''),
                len(elem['attributes']),
                len(elem['operations']),
                elem.get('author', '')
            ))
    
    def populate_diagrams(self):
        for item in self.diagrams_tree.get_children():
            self.diagrams_tree.delete(item)
        
        if not self.analysis_results:
            return
        
        diagrams = self.analysis_results['diagrams']
        packages = self.analysis_results['packages']
        
        for diag_id, diag in diagrams.items():
            package_name = ''
            if diag['package_id'] and diag['package_id'] in packages:
                package_name = packages[diag['package_id']]['name']
            
            self.diagrams_tree.insert('', tk.END, values=(
                diag['name'],
                diag['type'],
                package_name,
                len(diag['elements']),
                'Yes' if diag['has_image'] else 'No',
                diag.get('author', ''),
                diag.get('modified', '')
            ))
    
    def populate_relationships(self):
        for item in self.relationships_tree.get_children():
            self.relationships_tree.delete(item)
        
        if not self.analysis_results:
            return
        
        connectors = self.analysis_results['connectors']
        elements = self.analysis_results['elements']
        
        for conn_id, conn in connectors.items():
            source_name = ''
            target_name = ''
            
            if conn['source_id'] and conn['source_id'] in elements:
                source_name = elements[conn['source_id']]['name']
            
            if conn['target_id'] and conn['target_id'] in elements:
                target_name = elements[conn['target_id']]['name']
            
            self.relationships_tree.insert('', tk.END, values=(
                conn.get('name', ''),
                conn['type'],
                source_name,
                target_name,
                conn.get('direction', ''),
                conn.get('stereotype', '')
            ))
    
    def export_json(self):
        if not self.analysis_results:
            messagebox.showwarning("Warning", "No analysis results to export.")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Save Analysis as JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                # Convert sets to lists for JSON serialization
                json_results = self.analysis_results.copy()
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(json_results, f, indent=2, default=str)
                
                messagebox.showinfo("Success", f"Analysis exported to:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export JSON file:\n{e}")
    
    def generate_word_doc(self):
        if not self.analysis_results:
            messagebox.showwarning("Warning", "No analysis results available.")
            return
        
        messagebox.showinfo("Word Generation", 
                           "Word document generation will be implemented in the next phase.\n\n"
                           "This will include:\n"
                           "• Structured documentation with TOC\n"
                           "• Package hierarchy\n"
                           "• Element descriptions\n"
                           "• Relationship diagrams\n"
                           "• Embedded images\n"
                           "• Professional formatting")
    
    def show_package_hierarchy(self):
        if not self.analysis_results:
            messagebox.showwarning("Warning", "No analysis results available.")
            return
        
        # Create a new window to show package hierarchy
        hierarchy_window = tk.Toplevel(self.root)
        hierarchy_window.title("Package Hierarchy")
        hierarchy_window.geometry("600x400")
        
        tree = ttk.Treeview(hierarchy_window)
        tree.pack(fill=tk.BOTH, expand=True)
        
        packages = self.analysis_results['packages']
        
        # Build hierarchy (this is a simplified version)
        root_packages = [pkg for pkg in packages.values() if not pkg['parent_id']]
        
        for pkg in root_packages:
            self._add_package_to_tree(tree, '', pkg, packages)
    
    def _add_package_to_tree(self, tree, parent, package, all_packages):
        item = tree.insert(parent, tk.END, text=f"{package['name']} ({len(package['elements'])} elements)")
        
        for sub_pkg_id in package['sub_packages']:
            if sub_pkg_id in all_packages:
                self._add_package_to_tree(tree, item, all_packages[sub_pkg_id], all_packages)
    
    def show_relationships(self):
        if not self.analysis_results:
            messagebox.showwarning("Warning", "No analysis results available.")
            return
        
        messagebox.showinfo("Relationships", "Relationship visualization will be implemented in the next phase.")
    
    def show_diagrams(self):
        if not self.analysis_results:
            messagebox.showwarning("Warning", "No analysis results available.")
            return
        
        diagrams_with_images = [d for d in self.analysis_results['diagrams'].values() if d['has_image']]
        
        messagebox.showinfo("Diagrams", 
                           f"Found {len(self.analysis_results['diagrams'])} diagrams.\n"
                           f"{len(diagrams_with_images)} diagrams have embedded images.\n\n"
                           "Diagram viewer will be implemented in the next phase.")
    
    def clear_results(self):
        self.overview_text.delete(1.0, tk.END)
        
        for tree in [self.packages_tree, self.elements_tree, self.diagrams_tree, self.relationships_tree]:
            for item in tree.get_children():
                tree.delete(item)
    
    def debug_xml_structure(self):
        """Debug tool to show XML structure and find diagram-related elements"""
        if not self.current_file:
            messagebox.showwarning("Warning", "No XML file loaded.")
            return
        
        debug_window = tk.Toplevel(self.root)
        debug_window.title("XML Structure Debug")
        debug_window.geometry("800x600")
        
        notebook = ttk.Notebook(debug_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Tab 1: XML Structure Overview
        structure_frame = ttk.Frame(notebook)
        notebook.add(structure_frame, text="XML Structure")
        
        structure_text = scrolledtext.ScrolledText(structure_frame)
        structure_text.pack(fill=tk.BOTH, expand=True)
        
        # Tab 2: Diagram-related Elements
        diagrams_frame = ttk.Frame(notebook)
        notebook.add(diagrams_frame, text="Diagram Elements")
        
        diagrams_text = scrolledtext.ScrolledText(diagrams_frame)
        diagrams_text.pack(fill=tk.BOTH, expand=True)
        
        # Analyze XML structure
        try:
            tree = ET.parse(self.current_file)
            root = tree.getroot()
            
            # Generate structure overview
            structure_info = f"XML ROOT ELEMENT: {root.tag}\n"
            structure_info += f"Root Attributes: {dict(root.attrib)}\n\n"
            
            # Find all unique element types
            all_elements = {}
            for elem in root.iter():
                tag = elem.tag.split('}')[-1]  # Remove namespace
                if tag not in all_elements:
                    all_elements[tag] = {
                        'count': 0,
                        'sample_attributes': set(),
                        'has_text': False
                    }
                all_elements[tag]['count'] += 1
                all_elements[tag]['sample_attributes'].update(elem.attrib.keys())
                if elem.text and elem.text.strip():
                    all_elements[tag]['has_text'] = True
            
            structure_info += "ALL ELEMENT TYPES FOUND:\n" + "="*30 + "\n"
            for tag, info in sorted(all_elements.items()):
                structure_info += f"{tag}: {info['count']} occurrences\n"
                if info['sample_attributes']:
                    structure_info += f"  Attributes: {', '.join(list(info['sample_attributes'])[:10])}\n"
                if info['has_text']:
                    structure_info += f"  Has text content: Yes\n"
                structure_info += "\n"
            
            structure_text.insert(tk.END, structure_info)
            
            # Look for diagram-related content
            diagram_info = "DIAGRAM-RELATED ELEMENTS:\n" + "="*30 + "\n"
            
            # Search for anything that might be diagram-related
            diagram_keywords = ['diagram', 'image', 'metafile', 'png', 'jpg', 'bmp', 'drawing', 'graphic']
            
            for keyword in diagram_keywords:
                matches = []
                for elem in root.iter():
                    tag_lower = elem.tag.lower()
                    if keyword in tag_lower:
                        matches.append(elem)
                    # Also check attributes
                    for attr_name, attr_value in elem.attrib.items():
                        if keyword in attr_name.lower() or keyword in str(attr_value).lower():
                            matches.append(elem)
                
                if matches:
                    diagram_info += f"\nElements containing '{keyword}': {len(matches)}\n"
                    for i, elem in enumerate(matches[:5]):  # Show first 5 matches
                        diagram_info += f"  {i+1}. {elem.tag} - {dict(elem.attrib)}\n"
                        if elem.text and len(elem.text.strip()) > 0:
                            text_preview = elem.text.strip()[:100]
                            diagram_info += f"     Text: {text_preview}{'...' if len(elem.text.strip()) > 100 else ''}\n"
                    if len(matches) > 5:
                        diagram_info += f"     ... and {len(matches) - 5} more\n"
            
            # Check for base64-like content
            diagram_info += f"\nSEARCHING FOR BASE64 CONTENT:\n" + "="*25 + "\n"
            base64_candidates = []
            for elem in root.iter():
                if elem.text and len(elem.text.strip()) > 100:
                    text = elem.text.strip()
                    # Check if it looks like base64
                    if all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=' for c in text[:50]):
                        base64_candidates.append((elem.tag, len(text)))
            
            if base64_candidates:
                diagram_info += f"Found {len(base64_candidates)} potential base64 elements:\n"
                for tag, length in base64_candidates:
                    diagram_info += f"  {tag}: {length} characters\n"
            else:
                diagram_info += "No base64-like content found.\n"
            
            diagrams_text.insert(tk.END, diagram_info)
            
        except Exception as e:
            structure_text.insert(tk.END, f"Error analyzing XML: {e}")
    
    def search_xml_content(self):
        """Allow user to search for specific content in the XML"""
        if not self.current_file:
            messagebox.showwarning("Warning", "No XML file loaded.")
            return
        
        search_term = tk.simpledialog.askstring("Search XML", "Enter search term:")
        if not search_term:
            return
        
        search_window = tk.Toplevel(self.root)
        search_window.title(f"Search Results for: {search_term}")
        search_window.geometry("700x500")
        
        search_text = scrolledtext.ScrolledText(search_window)
        search_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        try:
            tree = ET.parse(self.current_file)
            root = tree.getroot()
            
            results = f"SEARCH RESULTS FOR: '{search_term}'\n" + "="*50 + "\n\n"
            matches_found = 0
            
            for elem in root.iter():
                # Check element tag
                if search_term.lower() in elem.tag.lower():
                    matches_found += 1
                    results += f"ELEMENT TAG MATCH #{matches_found}:\n"
                    results += f"  Tag: {elem.tag}\n"
                    results += f"  Attributes: {dict(elem.attrib)}\n"
                    if elem.text and elem.text.strip():
                        text_preview = elem.text.strip()[:200]
                        results += f"  Text: {text_preview}{'...' if len(elem.text.strip()) > 200 else ''}\n"
                    results += "\n"
                
                # Check attributes
                for attr_name, attr_value in elem.attrib.items():
                    if (search_term.lower() in attr_name.lower() or 
                        search_term.lower() in str(attr_value).lower()):
                        matches_found += 1
                        results += f"ATTRIBUTE MATCH #{matches_found}:\n"
                        results += f"  Element: {elem.tag}\n"
                        results += f"  Attribute: {attr_name} = {attr_value}\n"
                        results += f"  All Attributes: {dict(elem.attrib)}\n"
                        results += "\n"
                
                # Check text content
                if elem.text and search_term.lower() in elem.text.lower():
                    matches_found += 1
                    results += f"TEXT CONTENT MATCH #{matches_found}:\n"
                    results += f"  Element: {elem.tag}\n"
                    text_preview = elem.text.strip()[:500]
                    results += f"  Text: {text_preview}{'...' if len(elem.text.strip()) > 500 else ''}\n"
                    results += "\n"
            
            if matches_found == 0:
                results += f"No matches found for '{search_term}'"
            else:
                results = f"Found {matches_found} matches:\n\n" + results
            
            search_text.insert(tk.END, results)
            
        except Exception as e:
            search_text.insert(tk.END, f"Error searching XML: {e}")
    
    def show_about(self):
        about_text = """Enterprise Architect XML Analyzer v1.0

Comprehensive analysis tool for EA model exports.

Features:
• Complete model structure analysis
• Package hierarchy extraction
• Element and relationship mapping
• Diagram detection and image extraction
• Metadata and documentation extraction
• Word document generation (coming soon)
• XML structure debugging tools

Perfect for generating structured documentation from EA models."""
        
        messagebox.showinfo("About", about_text)


def main():
    root = tk.Tk()
    app = EAAnalyzerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()


def main():
    root = tk.Tk()
    app = EAAnalyzerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()