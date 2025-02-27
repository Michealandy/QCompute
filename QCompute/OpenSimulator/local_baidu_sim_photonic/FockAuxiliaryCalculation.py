#!/usr/bin/python3
# -*- coding: utf8 -*-

# Copyright (c) 2022 Baidu, Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Several auxiliary functions for the quantum circuit based on fock states
"""
import numpy
from typing import List


def CreateSubset(num_coincidence: int) -> List[list]:
    r"""
    According to a given positive integer :math:`n`,
    this function generates all subset of :math:`\left[ 1, 2, \dots, n \right]`.

    :param num_coincidence: the number of photons in single shot
    :return all_subset: all subset of :math:`\left[ 1, 2, \dots, n \right]`
    """

    num_arange = numpy.arange(num_coincidence)
    all_subset = []

    for index_1 in range(1, 2 ** num_coincidence):
        all_subset.append([])
        for index_2 in range(num_coincidence):
            if index_1 & (1 << index_2):
                all_subset[-1].append(num_arange[index_2])

    return all_subset


def RyserFormula(num_coincidence: int, U_st: numpy.ndarray) -> complex:
    r"""
    Calculate the permanent for a given submatrix

    :param num_coincidence: the number of photons in single shot
    :param U_st: the submatrix :math:`U_{\mathbf{st}}` of unitary :math:`U`,
                 where subscript :math:`\mathbf{s}` and :math:`\mathbf{t}` denote the input and output state, respectively.
    :return value_perm: permanent of input :math:`U_{\mathbf{st}}`
    """

    value_perm = 0
    set = CreateSubset(num_coincidence)

    for subset in set:
        num_elements = len(subset)
        value_times = 1
        for i in range(num_coincidence):
            value_sum = 0
            for j in subset:
                value_sum += U_st[i, j]
            value_times *= value_sum
        value_perm += value_times * (-1) ** num_elements
    value_perm *= (-1) ** num_coincidence
    return value_perm


def CreateSubMatrix(U: numpy.ndarray, input_state: numpy.ndarray, output_state: numpy.ndarray) -> numpy.ndarray:
    r"""
    Generate the submatrix for a given matrix

    :param U: an :math:`N \times N` square matrix
    :param input_state: input state for given number of photons
    :param output_state: output state for given number of photons
    :return U_st: submatrix of interferometer :math:`U`
    """

    in_eff_mode = numpy.nonzero(input_state)[0]
    out_eff_mode = numpy.nonzero(output_state)[0]

    row_submatrix = col_submatrix = []
    for coor_eff_mode in in_eff_mode:
        row_submatrix = numpy.append(row_submatrix, int(input_state[coor_eff_mode]) * [coor_eff_mode], axis=0)

    for coor_eff_mode in out_eff_mode:
        col_submatrix = numpy.append(col_submatrix, int(output_state[coor_eff_mode]) * [coor_eff_mode], axis=0)

    dim_U_st = len(row_submatrix)
    U_st = numpy.zeros((dim_U_st, dim_U_st), dtype=complex)
    for i in range(dim_U_st):
        for j in range(dim_U_st):
            coor_row = int(row_submatrix[i])
            coor_col = int(col_submatrix[j])
            U_st[i, j] = U[coor_col, coor_row]

    return U_st
