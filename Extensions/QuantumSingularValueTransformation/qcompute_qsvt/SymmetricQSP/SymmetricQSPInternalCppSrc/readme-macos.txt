macos 12.6 intel�����
macos xx.x M1 ���


����װbrew��
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

��cmake��
brew install cmake

����װbrew�� 3.9��
// see https://stackoverflow.com/questions/32578106/how-to-install-python-devel-in-mac-os
brew reinstall python@3.9
����which python���Ӧ�÷������ƣ�/usr/bin/python3
��Ҫ��ԭװpy 3.9�����Ҳ���������
������miniconda/anaconda�����������Ҳ���ͷ�ļ�����������⻷�����˳�


//����װlibomp(û����)��
//brew install libomp
//export CC=/usr/bin/clang
//export CXX=/usr/bin/clang++
//export CPPFLAGS="$CPPFLAGS -Xpreprocessor -fopenmp"
//export CFLAGS="$CFLAGS -I/usr/local/opt/libomp/include"
//export CXXFLAGS="$CXXFLAGS -I/usr/local/opt/libomp/include"
//export LDFLAGS="$LDFLAGS -Wl,-rpath,/usr/local/opt/libomp/lib -L/usr/local/opt/libomp/lib -lomp"

����Դ�����й�MKL��OPENMP���ٵ�ɾ����

����cmakelist���й�UNIX�µ�static-libgcc��һ����ɾ����macos�����á�

//����֤һ��Python headers��
// find / -name Python.h 2>/dev/null
// /Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/Headers/Python.h
// /System/Volumes/Data/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/Headers/Python.h
// �޸�cmake��������·��
// pip install pybind11?


�����롿
cd SymmetricQSPInternalCpp
mkdir build
cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make
ִ��ð�̲��Խű���һ��Ҫ���ԣ�һЩ��Ĺ�����ͨ��build������ִ�г���
