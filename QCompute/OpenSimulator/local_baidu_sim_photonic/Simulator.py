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
According to the type of gate or measurement implemented to quantum circuit, we can determine which circuit to run.
"""

import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Union, Dict, Optional

import numpy
from QCompute import Define
from QCompute.OpenConvertor.JsonToCircuit import JsonToCircuit
from QCompute.OpenSimulator import QPhotonicResult, ModuleErrorCode
from QCompute.QPlatform import Error
from QCompute.QPlatform.Processor.PreProcess import preProcess
from QCompute.QProtobuf import PBProgram, PBPhotonicGaussianGate, PBPhotonicGaussianMeasure, \
    PBPhotonicFockGate, PBPhotonicFockMeasure

FileErrorCode = 5


def runSimulator(args: Optional[List[str]], program: Optional['PBProgram']) -> 'QPhotonicResult':
    """
    Initialization process
    """

    isGaussian = False
    isFock = False
    for circuitLine in program.body.circuit:
        op = circuitLine.WhichOneof('op')
        if op not in ['photonicGaussianGate', 'photonicGaussianMeasure', 'photonicFockGate', 'photonicFockMeasure']:
            assert False
        elif op in ['photonicGaussianGate', 'photonicGaussianMeasure']:
            isGaussian = True
            if isFock:
                assert False
        elif op in ['photonicFockGate', 'photonicFockMeasure']:
            isFock = True
            if isGaussian:
                assert False

    if isGaussian:
        from QCompute.OpenSimulator.local_baidu_sim_photonic.InitGaussState import MatrixType
        from QCompute.OpenSimulator.local_baidu_sim_photonic.GaussTransfer import Algorithm
    elif isFock:
        from QCompute.OpenSimulator.local_baidu_sim_photonic.InitFockState import MatrixType
        from QCompute.OpenSimulator.local_baidu_sim_photonic.FockCalculateInterferometer import Algorithm
    else:
        assert False

    parser = argparse.ArgumentParser()
    parser.add_argument('-mt', default='dense', type=str)
    parser.add_argument('-a', default='matmul', type=str)

    parser.add_argument('-shots', default=None, type=int)
    parser.add_argument('-inputFile', default=None, type=str)

    args = parser.parse_args(args=args)
    matrixType: str = args.mt.lower()
    algorithm: str = args.a.lower()
    shots: int = args.shots  # shots=1 for Homo and Hetero measurement
    inputFile: str = args.inputFile

    if shots < 1 or shots > Define.maxShots:
        raise Error.ArgumentError(f'Invalid shots {shots}, should in [0, {Define.maxShots}]', ModuleErrorCode,
                                  FileErrorCode, 1)

    matrixTypeValue: Optional[MatrixType] = None
    if matrixType == 'dense':
        matrixTypeValue = MatrixType.Dense
    
    else:
        raise Error.ArgumentError(
            f'Invalid MatrixType {matrixTypeValue}', ModuleErrorCode, FileErrorCode, 2)

    algorithmValue: Optional[Algorithm] = None
    if algorithm == 'matmul':
        algorithmValue = Algorithm.Matmul
    elif algorithm == 'einsum':
        algorithmValue = Algorithm.Einsum
    else:
        raise Error.ArgumentError(
            f'Invalid Algorithm {algorithmValue}', ModuleErrorCode, FileErrorCode, 4)

    

    if inputFile is not None:
        jsonStr = Path(inputFile).read_text()
        program = JsonToCircuit().convert(jsonStr)

    if isGaussian:
        SV = GaussianCircuitVector(program, matrixTypeValue, algorithmValue, shots)
    elif isFock:
        SV = FockCircuitVector(program, matrixTypeValue, algorithmValue, shots)
    else:
        assert False
    return SV.core()


class GaussianCircuitVector:
    def __init__(self, program: 'PBProgram', matrixType: 'MatrixType', algorithm: 'Algorithm', shots: int) -> None:
        self.program = program
        self.matrixType = matrixType
        self.algorithm = algorithm
        self.shots = shots
        self.compactedCRegDict = None

    def core(self) -> 'QPhotonicResult':
        """
        Simulation process
        """

        program = self.program
        shots = self.shots

        usedQRegSet, usedCRegSet, compactedQRegDict, compactedCRegDict = preProcess(
            program, True, True)
        self.compactedCRegDict = compactedCRegDict

        # collect the result to simulator for the subsequent invoking
        result = QPhotonicResult()

        result.startTimeUtc = datetime.utcnow().isoformat()[:-3] + 'Z'
        result.value = self.core_without_photonic_noise()
        result.endTimeUtc = datetime.utcnow().isoformat()[:-3] + 'Z'

        result.shots = shots
        result.ancilla.usedQRegList = list(usedQRegSet)
        result.ancilla.usedCRegList = list(usedCRegSet)
        result.ancilla.compactedQRegDict = compactedQRegDict
        result.ancilla.compactedCRegDict = compactedCRegDict

        return result

    def core_without_photonic_noise(self) -> Dict[str, Union[float, int]]:
        """
        Simulation process for ideal circuit
        """
        from QCompute.QPlatform.QOperation.Photonic.PhotonicGaussianGate import PhotonicDX, PhotonicDP, PhotonicPHA, \
            PhotonicBS, PhotonicCZ, PhotonicCX, PhotonicDIS, PhotonicSQU, PhotonicTSQU, PhotonicMZ
        from QCompute.OpenSimulator.local_baidu_sim_photonic.InitGaussState import initState
        from QCompute.OpenSimulator.local_baidu_sim_photonic.GaussTransfer import GaussStateTransferProcessor
        from QCompute.OpenSimulator.local_baidu_sim_photonic.GaussHomoMea import HomodyneMeasure
        from QCompute.OpenSimulator.local_baidu_sim_photonic.GaussHeteroMea import HeterodyneMeasure
        from QCompute.OpenSimulator.local_baidu_sim_photonic.GaussPhotonCountMea import PhotonCountMeasure
        # if self.program is None:
        #     program = PBProgram()
        #     ParseDict(self.programDict, program)
        # else:
        #     program = self.program

        program = self.program
        matrixType = self.matrixType
        algorithm = self.algorithm
        shots = self.shots

        qRegMap = {qReg: index for index, qReg in enumerate(program.head.usingQRegList)}
        qRegCount = len(qRegMap)

        state_list = initState(matrixType, qRegCount)
        transfer = GaussStateTransferProcessor(matrixType, algorithm)
        homodyne_measurer = HomodyneMeasure(matrixType, algorithm)
        heterodyne_measurer = HeterodyneMeasure(matrixType, algorithm)
        photon_count_measurer = PhotonCountMeasure(matrixType, algorithm)
        measured = False
        for circuitLine in program.body.circuit:  # Traverse the circuit
            op = circuitLine.WhichOneof('op')

            qRegList = [qRegMap[qReg] for qReg in circuitLine.qRegList]  # type List[int]

            if op == 'photonicGaussianGate':
                photonicGaussianGate = circuitLine.photonicGaussianGate  # type: PBPhotonicGaussianGate
                gateName = PBPhotonicGaussianGate.Name(photonicGaussianGate)
                if gateName == 'PhotonicGaussianDX':
                    gate_list = PhotonicDX(*circuitLine.argumentValueList)
                elif gateName == 'PhotonicGaussianDP':
                    gate_list = PhotonicDP(*circuitLine.argumentValueList)
                elif gateName == 'PhotonicGaussianPHA':
                    gate_list = PhotonicPHA(*circuitLine.argumentValueList)
                elif gateName == 'PhotonicGaussianBS':
                    gate_list = PhotonicBS(*circuitLine.argumentValueList)
                elif gateName == 'PhotonicGaussianCZ':
                    gate_list = PhotonicCZ(*circuitLine.argumentValueList)
                elif gateName == 'PhotonicGaussianCX':
                    gate_list = PhotonicCX(*circuitLine.argumentValueList)
                elif gateName == 'PhotonicGaussianDIS':
                    gate_list = PhotonicDIS(*circuitLine.argumentValueList)
                elif gateName == 'PhotonicGaussianSQU':
                    gate_list = PhotonicSQU(*circuitLine.argumentValueList)
                elif gateName == 'PhotonicGaussianTSQU':
                    gate_list = PhotonicTSQU(*circuitLine.argumentValueList)
                elif gateName == 'PhotonicGaussianMZ':
                    gate_list = PhotonicMZ(*circuitLine.argumentValueList)
                else:
                    raise Error.ArgumentError(
                        f'Unsupported operation {PBPhotonicGaussianGate.Name(photonicGaussianGate)}!', ModuleErrorCode,
                        FileErrorCode,
                        8)
                state_list = transfer(state_list, gate_list, numpy.array(qRegList))

            elif op == 'photonicGaussianMeasure':
                measure: PBPhotonicGaussianMeasure = circuitLine.photonicGaussianMeasure
                if not measured:
                    measured = True
                if measure.type == PBPhotonicGaussianMeasure.Type.Homodyne:
                    assert (shots == 1)
                    result_measure = homodyne_measurer(state_list, numpy.array(qRegList), shots)
                elif measure.type == PBPhotonicGaussianMeasure.Type.Heterodyne:
                    assert (shots == 1)
                    result_measure = heterodyne_measurer(state_list, circuitLine.photonicGaussianMeasure.heterodyne,
                                                         numpy.array(qRegList), shots)
                elif measure.type == PBPhotonicGaussianMeasure.Type.PhotonCount:
                    assert (shots >= 1 and type(shots) == int)
                    result_measure = photon_count_measurer(state_list, circuitLine.photonicGaussianMeasure.photonCount,
                                                           shots)
                else:
                    raise Error.ArgumentError(
                        f'Unsupported operation measure {PBPhotonicGaussianMeasure.Type.Name(measure.type)}!',
                        ModuleErrorCode,
                        FileErrorCode, 13)

            else:
                raise Error.ArgumentError(f'Unsupported operation {op}!', ModuleErrorCode, FileErrorCode, 11)

        return result_measure


class FockCircuitVector:
    def __init__(self, program: 'PBProgram', matrixType: 'MatrixType', algorithm: 'Algorithm', shots: int) -> None:
        self.program = program
        self.matrixType = matrixType
        self.algorithm = algorithm
        self.shots = shots
        self.compactedCRegDict = None

    def core(self) -> 'QPhotonicResult':
        """
        Simulation process
        """
        program = self.program
        shots = self.shots

        usedQRegSet, usedCRegSet, compactedQRegDict, compactedCRegDict = preProcess(
            program, True, True)
        self.compactedCRegDict = compactedCRegDict

        # collect the result to simulator for the subsequent invoking
        result = QPhotonicResult()

        result.startTimeUtc = datetime.utcnow().isoformat()[:-3] + 'Z'
        result.value = self.core_without_photonic_noise()
        result.endTimeUtc = datetime.utcnow().isoformat()[:-3] + 'Z'

        result.shots = shots
        result.ancilla.usedQRegList = list(usedQRegSet)
        result.ancilla.usedCRegList = list(usedCRegSet)
        result.ancilla.compactedQRegDict = compactedQRegDict
        result.ancilla.compactedCRegDict = compactedCRegDict

        return result

    def core_without_photonic_noise(self) -> Dict[str, Union[float, int]]:
        """
        Simulation process for ideal circuit
        """

        from QCompute.QPlatform.QOperation.Photonic.PhotonicFockGate import PhotonicAP, PhotonicPHA, PhotonicBS, \
            PhotonicMZ
        from QCompute.OpenSimulator.local_baidu_sim_photonic.InitFockState import initState
        from QCompute.OpenSimulator.local_baidu_sim_photonic.FockCalculateInterferometer import FockStateTransferProcessor
        from QCompute.OpenSimulator.local_baidu_sim_photonic.FockAddPhotons import AddPhotonsToInitFockState
        from QCompute.OpenSimulator.local_baidu_sim_photonic.FockPhotonCountMeasure import PhotonCountMeasure
        # if self.program is None:
        #     program = PBProgram()
        #     ParseDict(self.programDict, program)
        # else:
        #     program = self.program
        program = self.program
        matrixType = self.matrixType
        algorithm = self.algorithm
        shots = self.shots

        qRegMap = {qReg: index for index, qReg in enumerate(program.head.usingQRegList)}
        qRegCount = len(qRegMap)

        fock_state_vector = initState(matrixType, qRegCount)
        add_photons = AddPhotonsToInitFockState(matrixType)
        calcu_unitary_trans = FockStateTransferProcessor(algorithm)
        unitary_trans_total = numpy.eye(qRegCount)
        photon_count_measurer = PhotonCountMeasure(matrixType, algorithm)
        measured = False
        for circuitLine in program.body.circuit:  # Traverse the circuit
            op = circuitLine.WhichOneof('op')

            qRegList = [qRegMap[qReg] for qReg in circuitLine.qRegList]  # type List[int]

            if op == 'photonicFockGate':
                photonicFockGate = circuitLine.photonicFockGate  # type: PBPhotonicFockGate
                gateName = PBPhotonicFockGate.Name(photonicFockGate)
                if gateName == 'PhotonicFockAP':
                    gate_matrix = PhotonicAP(*circuitLine.argumentValueList)
                    fock_state_vector = add_photons(fock_state_vector, gate_matrix, numpy.array(qRegList))
                else:
                    if gateName == 'PhotonicFockPHA':
                        gate_matrix = PhotonicPHA(*circuitLine.argumentValueList)
                    elif gateName == 'PhotonicFockBS':
                        gate_matrix = PhotonicBS(*circuitLine.argumentValueList)
                    elif gateName == 'PhotonicFockMZ':
                        gate_matrix = PhotonicMZ(*circuitLine.argumentValueList)
                    else:
                        raise Error.ArgumentError(
                            f'Unsupported operation {PBPhotonicFockGate.Name(photonicFockGate)}!', ModuleErrorCode,
                            FileErrorCode, 8)
                    unitary_trans_total = calcu_unitary_trans(unitary_trans_total, gate_matrix, numpy.array(qRegList))

            elif op == 'photonicFockMeasure':
                measure: PBPhotonicFockMeasure = circuitLine.photonicFockMeasure
                if not measured:
                    measured = True
                assert (shots >= 1 and type(shots) == int)
                result_measure = photon_count_measurer(fock_state_vector, unitary_trans_total,
                                                           measure.cutoff, shots)
            else:
                raise Error.ArgumentError(f'Unsupported operation {op}!', ModuleErrorCode, FileErrorCode, 11)

        return result_measure


if __name__ == '__main__':
    result = runSimulator(None, None)
    countsFilePath = Define.outputDirPath / 'counts.json'
    countsFilePath.write_text(result.toJson(True), encoding='utf-8')
