from pathlib import Path
import numpy as np
import zlib
import gzip
import nbtlib
import os
from io import BytesIO

dtypeReg = np.dtype([    
    ('offset_b', '>u4'),
    ('status', 'u1'),
    ('xPos', 'i4'),
    ('zPos', 'i4'),
    ('size', 'u1')
])

def get_region_folder():
    while True:
        path_str = input("Enter the path to the 'region' folder: ")
        #path_str = "C:\Files\Code\python\worldFix(2)\region"
        print(path_str)
        region_path = Path(path_str)
                
        if not region_path.is_dir():
            print(f"Error: '{path_str}' is not a folder or does not exist. Try again.")
            continue 

        if region_path.name == 'region':
            return region_path
        elif (region_path / 'region').is_dir():
            return region_path / 'region'
        else:
            print(f"Error: the specified folder does not contain a subfolder named 'region'. Try again.")
                  
def check_region_folder(region_path):
    mca_files = []
    invalid_objects = []
    
    for item in region_path.iterdir():
        if item.is_file() and item.suffix == '.mca':
            mca_files.append(item)
        else:
            invalid_objects.append(item)

    if invalid_objects:
        print("\nWarning: Invalid objects found in folder 'region':")
        for obj in invalid_objects:
            if obj.is_file():
                print(f"- File with invalid extension: {obj.name}")
            else:
                print(f"- Subfolder: {obj.name}")

    if not mca_files:
        print("Error: No files with extension .mca found in folder 'region'")
        exit(1)
        
    print(f"\nFound {len(mca_files)} files with extension .mca in folder 'region'")    
    return mca_files

def read_chunks_data(file_path, chunks_array):
    with open(file_path, "rb") as f:
        region_data = f.read()

    for i in range(0, 4096, 4):
        chunk_header = region_data[i:i+4]
        x, z = int((i/4)%32), int((i/4)//32),

        if chunk_header == b'\x00\x00\x00\x00':     #Не сгенерировался
            chunks_array[x, z]['status'] = 0
            continue

        chunks_array[x, z]['offset_b'] = int.from_bytes(chunk_header[:3], byteorder='big')
        chunks_array[x, z]['size'] = chunk_header[3]
        chunk_data = region_data[chunks_array[x, z]['offset_b'] * 4096 : (chunks_array[x, z]['offset_b'] + chunks_array[x, z]['size']) * 4096]
        compress_type = chunk_data[4]

        if (compress_type <= 0x01)or(0x03 <= compress_type): 
            chunks_array[x, z]['status'] = 5        #неверное шифрование, все сломано
            continue

        try:
            match compress_type:
                case 1:
                    decompressed = gzip.decompress(chunk_data[5:])
                case 2:
                    decompressed = zlib.decompress(chunk_data[5:])
                case 3:
                    decompressed = chunk_data[5:]
        except Exception as e:
            print(f"Chunk encryption method {compress_type}. Size {chunks_array[x, z]['size']}. {hex(chunks_array[x, z]['offset_b'] * 4096)} - {hex((chunks_array[x, z]['offset_b'] + chunks_array[x, z]['size']) * 4096 -1)} . Error processing chunk ({x}, {z}) in {file_path.stem}: {str(e)}")
            chunks_array[x, z]['status'] = 4        # Ошибка чтения
            continue

        nbt = nbtlib.File.parse(BytesIO(decompressed))
        chunks_array[x, z]['xPos'] = nbt['xPos']
        chunks_array[x, z]['zPos'] = nbt['zPos']
        parts = file_path.name.split('.')
        xReg, zReg = int(parts[1]), int(parts[2])

        if (x + xReg*32 == chunks_array[x, z]['xPos'])and(z + zReg*32 == chunks_array[x, z]['zPos']): 
            chunks_array[x, z]['status'] = 1        #на месте
        elif (xReg*32 <= chunks_array[x, z]['xPos'] < (xReg+1)*32)and(zReg*32 <= chunks_array[x, z]['zPos'] < (zReg+1)*32):
            chunks_array[x, z]['status'] = 2        #в нужном регионе, но не на месте
        else:
            chunks_array[x, z]['status'] = 3        #в другом регионе
            #print("find")

    return region_data[:4096]

def print_region(data, symbols):
    symbol_width = max(len(s) for s in symbols)
    
    # 1. Достаем значения status в правильном порядке: data[X][Z]
    status_array = np.array([[data[x][z]["status"] for x in range(32)] for z in range(32)])
        
    # 3. Выводим заголовок (координаты X)
    header = "   " + " ".join(f"{x:^{symbol_width}}" for x in range(32))
    print(header)
    
    # 4. Выводим строки с координатами Z
    for z in range(32):
        row_label = f"{z:<2}"  # Метка Z (вертикаль)
        row_data = " ".join(f"{symbols[val]:^{symbol_width}}" for val in status_array[z])
        print(f"{row_label} {row_data}")

def print_header(header):
    binary_data = header
    hex_str = binary_data.hex()  # Конвертируем в HEX-строку (без префиксов)
    
    # Разбиваем на пары HEX-символов (каждый байт = 2 символа)
    hex_pairs = [hex_str[i:i+2] for i in range(0, len(hex_str), 2)]
    
    # Группируем по `bytes_per_line` байт в строке
    for i in range(0, len(hex_pairs), 4):
        line = hex_pairs[i:i + 4]
        print(hex(i),"  "," ".join(line))  # Выводим HEX-байты через пробел

def print_region_list(chunks_array, range_x, range_z):
    for z in range_z:
        for x in range_x:
            print(f"[{x}, {z}]{chunks_array[x, z]}[{chunks_array[x, z]['xPos'] % 32}, {chunks_array[x, z]['zPos'] % 32}]")

def recreate_header(chunks_array):
    global d_chanks
    global r_chanks
    header = bytearray(0x1000)
    for z in range(32):
        for x in range(32):
            '''if chunks_array[x, z]['status'] in (4,5):
                d_chanks +=1
            if chunks_array[x, z]['status'] == 3:
                r_chanks +=1'''

            if chunks_array[x, z]['status'] in (0, 3, 4, 5):
                chunks_array[x, z]['status'] = 0
                continue
            rPos = ((chunks_array[x, z]['xPos'] % 32) + (chunks_array[x, z]['zPos'] % 32) * 32) * 4
            header[rPos : rPos + 3] = chunks_array[x, z]['offset_b'].item().to_bytes(4, byteorder='big')[1:]
            header[rPos + 3] = chunks_array[x, z]['size']
            
            if chunks_array[x, z]['status'] == 2:
                chunks_array[x, z]['status'] = 6
    return header

def repair_header(original_header_data, chunks_array):    
    header = bytearray(original_header_data)

    for z in range(32):
        for x in range(32):
            pos = (x + z * 32) * 4
            if chunks_array[x, z]['status'] in (0, 1):
                continue
            elif chunks_array[x, z]['status'] in (3, 4, 5):
                header[pos : pos + 4] = b'\x00\x00\x00\x00'
                chunks_array[x, z]['status'] = 0
                continue
            elif chunks_array[x, z]['status'] in (2, 6):
                '''if chunks_array[chunks_array[x, z]['xPos'] % 32, chunks_array[x, z]['zPos'] % 32]['status'] in (2, 6): #Если на реальной позиции есть хороший чанк
                    header[pos : pos + 4] = b'\x00\x00\x00\x00'
                    chunks_array[x, z]['status'] = 0
                    continue
                else:
                    rPos = ((chunks_array[x, z]['xPos'] % 32) + (chunks_array[x, z]['zPos'] % 32) * 32) * 4
                    header[rPos : rPos + 3] = chunks_array[x, z]['offset_b'].tobytes()[1:]
                    header[rPos + 3] = chunks_array[x, z]['size']
                    chunks_array[x, z]['status'] = 6    '''
                rPos = ((chunks_array[x, z]['xPos'] % 32) + (chunks_array[x, z]['zPos'] % 32) * 32) * 4
                header[rPos : rPos + 3] = chunks_array[x, z]['offset_b'].tobytes()[1:]
                header[rPos + 3] = chunks_array[x, z]['size']
                chunks_array[x, z]['status'] = 6

    #print(header.hex())
    #print_header(header[:400])
    return header

def rewrite_header(file_path, header):
    with open(file_path, 'r+b') as f:
        f.seek(0)
        f.write(header)
    return

def proc_region_file(file_path):
    chunks_array = np.zeros((32, 32), dtype=dtypeReg)
    header = read_chunks_data(file_path, chunks_array)
    
    #print_header(header[:40])
    #print_region_list(chunks_array, range(32), range(0, 3))
    #print_region(chunks_array," V.oX0")
    #header = repair_header(header, chunks_array)
    header = recreate_header(chunks_array)
    #print(header.hex())
    #print_region_list(chunks_array, range(32), range(0, 3))
    #print_region(chunks_array," V.oX0_")
    rewrite_header(file_path, header)

#d_chanks = 0
#r_chanks = 0

def main():
    region_path = get_region_folder()
    mca_files = check_region_folder(region_path)
    for i in range(len(mca_files)):        
        print("file №", i, mca_files[i].name)
        proc_region_file(region_path / mca_files[i].name)
    #print("Удалённых чанков:", d_chanks)
    #print("Убежавших чанков:", r_chanks)
    print("end")
    
    
       

if __name__ == "__main__":
    main()
