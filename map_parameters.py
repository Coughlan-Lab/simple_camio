import numpy as np

# position of the aruco markers corners in cm
obj = np.empty((16, 3), dtype=np.float32)
# Marker 0
obj[0, :] = [0, 0, 0]
obj[1, :] = [2, 0, 0]
obj[2, :] = [2, 2, 0]
obj[3, :] = [0, 2, 0]
# Marker 1
obj[4, :] = [18, 0, 0]
obj[5, :] = [18 + 2, 0, 0]
obj[6, :] = [18 + 2, 2, 0]
obj[7, :] = [18, 2, 0]
# Marker 2
obj[8, :] = [0, 24, 0]
obj[9, :] = [2, 24, 0]
obj[10, :] = [2, 26, 0]
obj[11, :] = [0, 26, 0]
# Marker 3
obj[12, :] = [18, 24, 0]
obj[13, :] = [18 + 2, 24, 0]
obj[14, :] = [18 + 2, 26, 0]
obj[15, :] = [18, 26, 0]

map_dict = {1: "Broadway",
            2: "Pacific Avenue",
            3: "Jackson Street",
            4: "Washington Street",
            5: "Clay Street",
            6: "Sacramento Street",
            7: "California Street",
            8: "Pine Street",
            9: "Bush Street",
            10: "Sutter Street",
            11: "Scott Street",
            12: "Pierce Street",
            13: "Steiner Street",
            14: "Fillmore Street",
            15: "Webster Street",
            16: "Buchanan Street",
            17: "Alta Plaza Park",
            18: "Smith-Kettlewell Eye Research Institute",
            19: "Orben Place",
            20: "Wilmot Street"}

sound_dict = {1: "01 Broadway.mp3",
              2: "02 Pacific.mp3",
              3: "03 Jackson.mp3",
              4: "04 Washington.mp3",
              5: "05 Clay.mp3",
              6: "06 Sacramento.mp3",
              7: "07 California.mp3",
              8: "08 Pine.mp3",
              9: "09 Bush.mp3",
              10: "10 Sutter.mp3",
              11: "11 Scott.mp3",
              12: "12 Pierce.mp3",
              13: "13 Steiner.mp3",
              14: "14 Fillmore.mp3",
              15: "15 Webster.mp3",
              16: "16 Buchanan.mp3",
              17: "17 Alta Plaza Park.mp3",
              18: "18 Smith-Kettlewell.mp3",
              19: "19 Orben.mp3",
              20: "20 Wilmot.mp3"}
