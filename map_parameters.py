import numpy as np

# position of the aruco markers corners in cm
obj = np.empty((16, 3), dtype=np.float32)
# Marker 0
obj[0, :] = [0, 0, 0]
obj[1, :] = [2, 0, 0]
obj[2, :] = [2, 2, 0]
obj[3, :] = [0, 2, 0]
# Marker 1
obj[4, :] = [17, 0, 0]
obj[5, :] = [17 + 2, 0, 0]
obj[6, :] = [17 + 2, 2, 0]
obj[7, :] = [17, 2, 0]
# Marker 2
obj[8, :] = [0, 24, 0]
obj[9, :] = [2, 24, 0]
obj[10, :] = [2, 26, 0]
obj[11, :] = [0, 26, 0]
# Marker 3
obj[12, :] = [17, 24, 0]
obj[13, :] = [17 + 2, 24, 0]
obj[14, :] = [17 + 2, 26, 0]
obj[15, :] = [17, 26, 0]

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

map_dict_ukraine = {1: "Khreschatyk St.",
                    2: "Mykhailivs'ka St.",
                    3: "Mala Zhytomyrska St.",
                    4: "Sofiivs'ka St.",
                    5: "Tarasa Shevchenka Ln.",
                    6: "Borysa Hrinchenka St.",
                    7: "Kostolna St.",
                    8: "Heroyiv Nebesnoyi Sotni Alley",
                    9: "Arkhitektora Horodetskoho St.",
                    10: "Triokhsviatytelska St.",
                    11: "Mykhailivs'kyi Ln.",
                    12: "Prorizna St.",
                    13: "Malopidvalna St.",
                    14: "Volodymyrs'kyi Passage",
                    15: "Independence Square",
                    16: "St. Michael's Golden-Domed Monastery",
                    17: "Velyka Zhytomyrska St.",
                    18: "Volodymyrs'kyi descent"}

sound_dict_ukraine = {1: "Khreschyatik.mp3",
                      2: "Mikhaylivska St.mp3",
                      3: "Mala Zhytomirska.mp3",
                      4: "Sofiivska.mp3",
                      5: "Taras Shevchenko.mp3",
                      6: "Boris Hrinchenka.mp3",
                      7: "Kostolna.mp3",
                      8: "Heroiv Nebesnoi Sotni.mp3",
                      9: "Arkhitektora Horodestoho.mp3",
                      10:"Tryokhsvyatitelska St.mp3",
                      11:"Mikhaylivskiy Ln.mp3",
                      12:"Prorizna.mp3",
                      13:"Malopidvalna.mp3",
                      14:"Volodymirskiy Passage.mp3",
                      15:"Maidan.mp3",
                      16:"StMichael's Monastery.mp3",
                      17:"Velika Zhytomirska St.mp3",
                      18:"Volodymirskiy Descent.mp3"}