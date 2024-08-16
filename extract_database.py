import os
import pandas as pd
import requests
from Bio import PDB
import numpy as np
from Bio.SeqUtils import seq1
from lxml import etree

pdb_list = PDB.PDBList()
parser = PDB.PDBParser()


def get_uniprot_dataframe(xml_file):
    data = []
    context = etree.iterparse(xml_file, events=('end',), tag='{http://uniprot.org/uniprot}entry')
    for event, elem in context:
        accession = elem.findtext('{http://uniprot.org/uniprot}accession')
        sequence = elem.findtext('{http://uniprot.org/uniprot}sequence')
        protein_names = [name.text for name in elem.findall('.//{http://uniprot.org/uniprot}fullName')]
        organism = elem.findtext('.//{http://uniprot.org/uniprot}organism/{http://uniprot.org/uniprot}name')
        function = elem.findtext('.//{http://uniprot.org/uniprot}comment[@type="function"]/{http://uniprot.org/uniprot}text')
        subcellular_location = elem.findtext('.//{http://uniprot.org/uniprot}comment[@type="subcellular location"]/{http://uniprot.org/uniprot}subcellularLocation/{http://uniprot.org/uniprot}location')
        tissue_specificity = elem.findtext('.//{http://uniprot.org/uniprot}comment[@type="tissue specificity"]/{http://uniprot.org/uniprot}text')
        domain_structure = [domain.get('description') for domain in
                            elem.findall('.//{http://uniprot.org/uniprot}feature[@type="domain"]')]
        ptms = [ptm.get('description') for ptm in
                elem.findall('.//{http://uniprot.org/uniprot}feature[@type="modified residue"]')]
        interactions = [interaction.text for interaction in
                        elem.findall('.//{http://uniprot.org/uniprot}interactant/{http://uniprot.org/uniprot}geneName')]
        sequence_annotations = [(annot.get('description'), annot.get('evidence')) for annot in
                                elem.findall('.//{http://uniprot.org/uniprot}feature')]

        try:
            pdb_files = download_pdb_files_from_uniprot(accession)
            if pdb_files:
                structure = parser.get_structure(accession, pdb_files[0])  # Use the first PDB file
                coords, contact_map = get_coords_and_contact_map(structure)
                structure_info = get_structure_info(structure)
            else:
                coords = None
                contact_map = None
                structure_info = None
        except Exception as e:
            print(f"Error processing {accession}: {e}")
            contact_map = None
            structure_info = None

        data.append({
            'accession': accession,
            'sequence': sequence,
            'protein_names': protein_names,
            'organism': organism,
            'function': function,
            'subcellular_location': subcellular_location,
            'tissue_specificity': tissue_specificity,
            'domain_structure': domain_structure,
            'ptms': ptms,
            'interactions': interactions,
            'sequence_annotations': sequence_annotations,
            "coords": coords,
            "contact_map": contact_map,
            "structure_info": structure_info
        })
        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]

    return pd.DataFrame(data)


def download_pdb_files_from_uniprot(uniprot_id, pdb_dir='pdb_files'):
    pdb_ids = fetch_pdb_ids(uniprot_id)
    if not pdb_ids:
        return []

    downloaded_files = []
    for pdb_id in pdb_ids:
        pdb_path = download_pdb(pdb_id, pdb_dir=pdb_dir)
        downloaded_files.append(pdb_path)
    return downloaded_files


def fetch_pdb_ids(uniprot_id):
    url = f"https://www.uniprot.org/uniprot/{uniprot_id}.xml"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to retrieve data for {uniprot_id}")
        return None

    # Parse XML to find PDB IDs
    tree = etree.fromstring(response.content)
    pdb_ids = []
    for db_reference in tree.findall(".//{http://uniprot.org/uniprot}dbReference[@type='PDB']"):
        pdb_id = db_reference.get('id')
        pdb_ids.append(pdb_id)
    return pdb_ids


def download_pdb(pdb_id, pdb_dir='pdb_files'):
    if not os.path.exists(pdb_dir):
        os.makedirs(pdb_dir)
    pdb_list.retrieve_pdb_file(pdb_id, pdir=pdb_dir, file_format='pdb')
    return os.path.join(pdb_dir, f'pdb{pdb_id.lower()}.ent')


# 3. Function to extract sequence from PDB structure
def get_sequence(structure):
    sequence = ""
    for model in structure:
        for chain in model:
            for residue in chain:
                if residue.id[0] == " ":  # Exclude hetero atoms
                    sequence += seq1(residue.resname)
    return sequence


# 4. Function to generate contact map
def get_coords_and_contact_map(structure, threshold=8.0):
    atoms = list(structure.get_atoms())
    num_atoms = len(atoms)

    coords = []
    contact_map = np.zeros((num_atoms, num_atoms))

    for i in range(num_atoms):
        coords.append(atoms[i].coord)
        for j in range(i + 1, num_atoms):
            distance = atoms[i] - atoms[j]
            if distance < threshold:
                contact_map[i, j] = 1
                contact_map[j, i] = 1
    return coords, contact_map


# 5. Function to extract structure info
def get_structure_info(structure):
    return {
        "num_chains": len(list(structure.get_chains())),
        "num_residues": len(list(structure.get_residues())),
        "num_atoms": len(list(structure.get_atoms()))
    }


df = get_uniprot_dataframe(r"D:\python project\data\uniprot_sprot.xml\uniprot_sprot.xml")
df.to_csv("protein_df.csv", index=False)

print(df.head())
