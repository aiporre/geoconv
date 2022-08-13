from geoconv.preprocessing.barycentric_coords import create_kernel_matrix, barycentric_coordinates
from geoconv.preprocessing.discrete_gpc import discrete_gpc

import os
import tqdm
import numpy as np
import scipy
import shutil
import trimesh
import pyshot


def preprocess(directory, target_dir, reference_mesh):
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    file_list = os.listdir(directory)
    file_list.sort()
    file_list = [f for f in file_list if f[-4:] != ".png"]

    ######################
    # Load reference mesh
    ######################
    reference_mesh = trimesh.load_mesh(reference_mesh)

    with tqdm.tqdm(total=len(file_list)) as pbar:
        for file_no, file in enumerate(file_list):
            pbar.set_postfix({"Step": "Sub-sample the original meshes"})
            ############
            # Load mesh
            ############
            mesh = trimesh.load_mesh(f"{directory}/{file}")

            pbar.set_postfix({"Step": "Ground-truth computation"})
            ################
            # Shuffle nodes
            ################
            # Otherwise ground-truth matrix is unit-matrix all the time
            shuffled_node_indices = np.arange(mesh.vertices.shape[0])
            np.random.shuffle(shuffled_node_indices)
            object_mesh_vertices = np.copy(mesh.vertices)[shuffled_node_indices]
            object_mesh_faces = np.copy(mesh.faces)
            for face in object_mesh_faces:
                face[0] = np.where(shuffled_node_indices == face[0])[0]
                face[1] = np.where(shuffled_node_indices == face[1])[0]
                face[2] = np.where(shuffled_node_indices == face[2])[0]
            mesh = trimesh.Trimesh(vertices=object_mesh_vertices, faces=object_mesh_faces)

            ##########################
            # Set ground-truth labels
            ##########################
            label_matrix = np.zeros(
                shape=(np.array(mesh.vertices).shape[0], np.array(reference_mesh.vertices).shape[0]), dtype=np.int8
            )
            # For vertex mesh.vertices[i] ground truth is given by shuffled_node_indices[i]
            label_matrix[(np.arange(label_matrix.shape[0]), shuffled_node_indices)] = 1
            label_matrix = scipy.sparse.csc_array(label_matrix)
            np.save(f"{target_dir}/GT_{file[:-4]}.npy", label_matrix)

            pbar.set_postfix({"Step": "Compute SHOT descriptors"})
            ###########################
            # Compute SHOT descriptors
            ###########################
            descriptors = pyshot.get_descriptors(
                np.array(mesh.vertices),
                np.array(mesh.faces, dtype=np.int64),
                radius=100,
                local_rf_radius=.1,
                min_neighbors=3,
                n_bins=8,
                double_volumes_sectors=False,
                use_interpolation=True,
                use_normalization=True,
            ).astype(np.float32)
            np.save(f"{target_dir}/SHOT_{file[:-4]}.npy", descriptors)

            pbar.set_postfix({"Step": "Compute local GPC-systems"})
            ############################
            # Compute local GPC-systems
            ############################
            local_gpc_systems = discrete_gpc(
                mesh, u_max=0.05, eps=.000001, use_c=True, tqdm_msg=f"File {file_no} - Compute local GPC-systems"
            ).astype(np.float64)

            pbar.set_postfix({"Step": "Compute Barycentric coordinates"})
            ##################################
            # Compute Barycentric coordinates
            ##################################
            kernel = create_kernel_matrix(n_radial=2, n_angular=4, radius=0.04)
            bary_coords = barycentric_coordinates(
                local_gpc_systems, kernel, mesh, tqdm_msg=f"File {file_no} - Compute Barycentric coordinates"
            )
            np.save(f"{target_dir}/BC_{file[:-4]}.npy", bary_coords)

            pbar.update(1)

    shutil.make_archive(target_dir, "zip", target_dir)
    shutil.rmtree(target_dir)
    print("Preprocessing finished.")
