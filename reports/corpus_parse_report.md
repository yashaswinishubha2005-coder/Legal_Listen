# Law corpus parse report

Text is copied from the PDFs only. Nothing is written from memory.

| Act | File | Pages | Sections parsed | Warnings |
|---|---|---|---|---|
| BNS | nyaya.pdf | 112 | 352 | 1 |
| BNSS | nagarik.pdf | 282 | 528 | 1 |
| BSA | sakshya.pdf | 54 | 170 | 0 |
| ITA | information_technology.pdf | 44 | 118 | 25 |
| CPA | consumer.pdf | 42 | 104 | 3 |
| HMA | hindu_marriage.pdf | 17 | 35 | 1 |
| HSA | hindu_succession.pdf | 17 | 32 | 0 |
| SMA | special_marriage.pdf | 30 | 52 | 1 |
| PWDV | domestic_violence.pdf | 15 | 38 | 2 |
| DPA | dowry.pdf | 9 | 13 | 0 |
| GWA | guardian.pdf | 17 | 49 | 1 |
| TPA | transfer_of_property.pdf | 46 | 136 | 6 |
| RA | registration.pdf | 64 | 105 | 4 |
| SRA | specific_relief.pdf | 20 | 46 | 0 |
| LIMA | limitation.pdf | 27 | 36 | 1 |
| KLRA | land_revenue.pdf | 145 | 258 | 103 |
| IPC | penal_code.pdf | 119 | 558 | 206 |
| CrPC | **missing** (expected `*criminal*procedure*.pdf`) | – | 0 | – |
| IEA | evidence_act.pdf | 61 | 181 | 1 |

**Total sections:** 2811

## Missing PDFs

Place the official bare-act PDFs (e.g. from indiacode.nic.in) in `data/raw/acts/` with names matching the patterns below, then run `make corpus`.

- CrPC — Code of Criminal Procedure, 1973 (`*criminal*procedure*.pdf`)

## Warnings

### BNS

- missing section numbers (not found in PDF text): [147, 153, 154, 181, 209, 255]

### BNSS

- missing section numbers (not found in PDF text): [112, 231, 455]

### ITA

- ITA s.67: section 67 after 266: out of order
- ITA s.68: section 68 after 266: out of order
- ITA s.69: section 69 after 266: out of order
- ITA s.70: section 70 after 266: out of order
- ITA s.71: section 71 after 266: out of order
- ITA s.72: section 72 after 266: out of order
- ITA s.73: section 73 after 266: out of order
- ITA s.74: section 74 after 266: out of order
- ITA s.75: section 75 after 266: out of order
- ITA s.76: section 76 after 266: out of order
- ITA s.77: section 77 after 266: out of order
- ITA s.78: section 78 after 266: out of order
- ITA s.79: section 79 after 266: out of order
- ITA s.80: section 80 after 266: out of order
- ITA s.81: section 81 after 266: out of order
- ITA s.82: section 82 after 266: out of order
- ITA s.83: section 83 after 266: out of order
- ITA s.84: section 84 after 266: out of order
- ITA s.85: section 85 after 266: out of order
- ITA s.86: section 86 after 266: out of order
- ITA s.87: section 87 after 266: out of order
- ITA s.88: section 88 after 266: out of order
- ITA s.89: section 89 after 266: out of order
- ITA s.90: section 90 after 266: out of order
- missing section numbers (not found in PDF text): [20, 50, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128]…

### CPA

- CPA s.1: duplicate section number 1 (cross-reference or schedule?)
- CPA s.1: section 1 after 2: out of order
- missing section numbers (not found in PDF text): [13, 30, 44, 71]

### HMA

- missing section numbers (not found in PDF text): [6]

### SMA

- missing section numbers (not found in PDF text): [33, 35]

### PWDV

- PWDV s.4: duplicate section number 4 (cross-reference or schedule?)
- PWDV s.4: section 4 after 37: out of order

### GWA

- missing section numbers (not found in PDF text): [2, 5, 16, 29]

### TPA

- TPA s.2: section 2 after 5: out of order
- TPA s.3: section 3 after 5: out of order
- TPA s.5: duplicate section number 5 (cross-reference or schedule?)
- TPA s.1: duplicate section number 1 (cross-reference or schedule?)
- TPA s.1: section 1 after 7: out of order
- missing section numbers (not found in PDF text): [4, 74, 75, 80, 85, 86, 87, 88, 89, 90, 97, 99]

### RA

- RA s.18A: duplicate section number 18A (cross-reference or schedule?)
- RA s.80B: duplicate section number 80B (cross-reference or schedule?)
- RA s.80B: duplicate section number 80B (cross-reference or schedule?)
- missing section numbers (not found in PDF text): [9, 56, 67]

### LIMA

- missing section numbers (not found in PDF text): [28, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 62, 64, 65, 66, 67, 68, 69, 70, 71, 72]…

### KLRA

- KLRA s.2: duplicate section number 2 (cross-reference or schedule?)
- KLRA s.2: section 2 after 94: out of order
- KLRA s.1: duplicate section number 1 (cross-reference or schedule?)
- KLRA s.1: section 1 after 202: out of order
- KLRA s.3: duplicate section number 3 (cross-reference or schedule?)
- KLRA s.3: section 3 after 202: out of order
- KLRA s.1: duplicate section number 1 (cross-reference or schedule?)
- KLRA s.1: section 1 after 202: out of order
- KLRA s.1: duplicate section number 1 (cross-reference or schedule?)
- KLRA s.1: section 1 after 202: out of order
- KLRA s.2: duplicate section number 2 (cross-reference or schedule?)
- KLRA s.2: section 2 after 202: out of order
- KLRA s.3: duplicate section number 3 (cross-reference or schedule?)
- KLRA s.3: section 3 after 202: out of order
- KLRA s.1: duplicate section number 1 (cross-reference or schedule?)
- KLRA s.1: section 1 after 202: out of order
- KLRA s.1: duplicate section number 1 (cross-reference or schedule?)
- KLRA s.1: section 1 after 202: out of order
- KLRA s.1: duplicate section number 1 (cross-reference or schedule?)
- KLRA s.1: section 1 after 202: out of order
- KLRA s.1: duplicate section number 1 (cross-reference or schedule?)
- KLRA s.1: section 1 after 202: out of order
- KLRA s.1: duplicate section number 1 (cross-reference or schedule?)
- KLRA s.1: section 1 after 202: out of order
- KLRA s.1: duplicate section number 1 (cross-reference or schedule?)
- KLRA s.1: section 1 after 202: out of order
- KLRA s.1: duplicate section number 1 (cross-reference or schedule?)
- KLRA s.1: section 1 after 202: out of order
- KLRA s.1: duplicate section number 1 (cross-reference or schedule?)
- KLRA s.1: section 1 after 202: out of order
- KLRA s.1: duplicate section number 1 (cross-reference or schedule?)
- KLRA s.1: section 1 after 202: out of order
- KLRA s.1: duplicate section number 1 (cross-reference or schedule?)
- KLRA s.1: section 1 after 202: out of order
- KLRA s.1: duplicate section number 1 (cross-reference or schedule?)
- KLRA s.1: section 1 after 202: out of order
- KLRA s.1: duplicate section number 1 (cross-reference or schedule?)
- KLRA s.1: section 1 after 202: out of order
- KLRA s.1: duplicate section number 1 (cross-reference or schedule?)
- KLRA s.1: section 1 after 202: out of order
- KLRA s.3: duplicate section number 3 (cross-reference or schedule?)
- KLRA s.3: section 3 after 202: out of order
- KLRA s.4: section 4 after 202: out of order
- KLRA s.1: duplicate section number 1 (cross-reference or schedule?)
- KLRA s.1: section 1 after 202: out of order
- KLRA s.3: duplicate section number 3 (cross-reference or schedule?)
- KLRA s.3: section 3 after 202: out of order
- KLRA s.1: duplicate section number 1 (cross-reference or schedule?)
- KLRA s.1: section 1 after 202: out of order
- KLRA s.3: duplicate section number 3 (cross-reference or schedule?)
- KLRA s.3: section 3 after 202: out of order
- KLRA s.10: duplicate section number 10 (cross-reference or schedule?)
- KLRA s.10: section 10 after 202: out of order
- KLRA s.11: duplicate section number 11 (cross-reference or schedule?)
- KLRA s.11: section 11 after 202: out of order
- KLRA s.1: duplicate section number 1 (cross-reference or schedule?)
- KLRA s.1: section 1 after 202: out of order
- KLRA s.2: duplicate section number 2 (cross-reference or schedule?)
- KLRA s.2: section 2 after 202: out of order
- KLRA s.3: duplicate section number 3 (cross-reference or schedule?)
- KLRA s.3: section 3 after 202: out of order
- KLRA s.4: duplicate section number 4 (cross-reference or schedule?)
- KLRA s.4: section 4 after 202: out of order
- KLRA s.5: duplicate section number 5 (cross-reference or schedule?)
- KLRA s.5: section 5 after 202: out of order
- KLRA s.2: duplicate section number 2 (cross-reference or schedule?)
- KLRA s.2: section 2 after 202: out of order
- KLRA s.3: duplicate section number 3 (cross-reference or schedule?)
- KLRA s.3: section 3 after 202: out of order
- KLRA s.4: duplicate section number 4 (cross-reference or schedule?)
- KLRA s.4: section 4 after 202: out of order
- KLRA s.7: section 7 after 202: out of order
- KLRA s.8: duplicate section number 8 (cross-reference or schedule?)
- KLRA s.8: section 8 after 202: out of order
- KLRA s.9: duplicate section number 9 (cross-reference or schedule?)
- KLRA s.9: section 9 after 202: out of order
- KLRA s.10: duplicate section number 10 (cross-reference or schedule?)
- KLRA s.10: section 10 after 202: out of order
- KLRA s.11: duplicate section number 11 (cross-reference or schedule?)
- KLRA s.11: section 11 after 202: out of order
- KLRA s.12: duplicate section number 12 (cross-reference or schedule?)
- KLRA s.12: section 12 after 202: out of order
- KLRA s.13: duplicate section number 13 (cross-reference or schedule?)
- KLRA s.13: section 13 after 202: out of order
- KLRA s.14: duplicate section number 14 (cross-reference or schedule?)
- KLRA s.14: section 14 after 202: out of order
- KLRA s.16: duplicate section number 16 (cross-reference or schedule?)
- KLRA s.16: section 16 after 202: out of order
- KLRA s.17: duplicate section number 17 (cross-reference or schedule?)
- KLRA s.17: section 17 after 202: out of order
- KLRA s.18: duplicate section number 18 (cross-reference or schedule?)
- KLRA s.18: section 18 after 202: out of order
- KLRA s.19: duplicate section number 19 (cross-reference or schedule?)
- KLRA s.19: section 19 after 202: out of order
- KLRA s.22: duplicate section number 22 (cross-reference or schedule?)
- KLRA s.22: section 22 after 202: out of order
- KLRA s.25: duplicate section number 25 (cross-reference or schedule?)
- KLRA s.25: section 25 after 202: out of order
- KLRA s.2: duplicate section number 2 (cross-reference or schedule?)
- KLRA s.2: section 2 after 202: out of order
- KLRA s.3: duplicate section number 3 (cross-reference or schedule?)
- KLRA s.3: section 3 after 202: out of order
- missing section numbers (not found in PDF text): [61, 106, 147, 198]

### IPC

- IPC s.1: section 1 after 213: out of order
- IPC s.2: section 2 after 213: out of order
- IPC s.3: section 3 after 213: out of order
- IPC s.4: section 4 after 213: out of order
- IPC s.1: duplicate section number 1 (cross-reference or schedule?)
- IPC s.1: section 1 after 213: out of order
- IPC s.5: section 5 after 213: out of order
- IPC s.6: section 6 after 213: out of order
- IPC s.7: section 7 after 213: out of order
- IPC s.8: section 8 after 213: out of order
- IPC s.9: section 9 after 213: out of order
- IPC s.10: section 10 after 213: out of order
- IPC s.11: section 11 after 213: out of order
- IPC s.12: section 12 after 213: out of order
- IPC s.14: section 14 after 213: out of order
- IPC s.18: section 18 after 213: out of order
- IPC s.19: section 19 after 213: out of order
- IPC s.20: section 20 after 213: out of order
- IPC s.21: section 21 after 213: out of order
- IPC s.22: section 22 after 213: out of order
- IPC s.23: section 23 after 213: out of order
- IPC s.24: section 24 after 213: out of order
- IPC s.25: section 25 after 213: out of order
- IPC s.26: section 26 after 213: out of order
- IPC s.27: section 27 after 213: out of order
- IPC s.28: section 28 after 213: out of order
- IPC s.29: section 29 after 213: out of order
- IPC s.30: section 30 after 213: out of order
- IPC s.31: section 31 after 213: out of order
- IPC s.32: section 32 after 213: out of order
- IPC s.33: section 33 after 213: out of order
- IPC s.34: section 34 after 213: out of order
- IPC s.35: section 35 after 213: out of order
- IPC s.36: section 36 after 213: out of order
- IPC s.37: section 37 after 213: out of order
- IPC s.38: section 38 after 213: out of order
- IPC s.39: section 39 after 213: out of order
- IPC s.40: section 40 after 213: out of order
- IPC s.41: section 41 after 213: out of order
- IPC s.42: section 42 after 213: out of order
- IPC s.43: section 43 after 213: out of order
- IPC s.44: section 44 after 213: out of order
- IPC s.45: section 45 after 213: out of order
- IPC s.46: section 46 after 213: out of order
- IPC s.47: section 47 after 213: out of order
- IPC s.48: section 48 after 213: out of order
- IPC s.49: section 49 after 213: out of order
- IPC s.50: section 50 after 213: out of order
- IPC s.51: section 51 after 213: out of order
- IPC s.52: section 52 after 213: out of order
- IPC s.53: section 53 after 213: out of order
- IPC s.54: section 54 after 213: out of order
- IPC s.55: section 55 after 213: out of order
- IPC s.57: section 57 after 213: out of order
- IPC s.60: section 60 after 213: out of order
- IPC s.63: section 63 after 213: out of order
- IPC s.64: section 64 after 213: out of order
- IPC s.65: section 65 after 213: out of order
- IPC s.66: section 66 after 213: out of order
- IPC s.67: section 67 after 213: out of order
- IPC s.68: section 68 after 213: out of order
- IPC s.69: section 69 after 213: out of order
- IPC s.70: section 70 after 213: out of order
- IPC s.71: section 71 after 213: out of order
- IPC s.72: section 72 after 213: out of order
- IPC s.73: section 73 after 213: out of order
- IPC s.74: section 74 after 213: out of order
- IPC s.75: section 75 after 213: out of order
- IPC s.76: section 76 after 213: out of order
- IPC s.77: section 77 after 213: out of order
- IPC s.78: section 78 after 213: out of order
- IPC s.79: section 79 after 213: out of order
- IPC s.80: section 80 after 213: out of order
- IPC s.81: section 81 after 213: out of order
- IPC s.82: section 82 after 213: out of order
- IPC s.83: section 83 after 213: out of order
- IPC s.84: section 84 after 213: out of order
- IPC s.85: section 85 after 213: out of order
- IPC s.86: section 86 after 213: out of order
- IPC s.87: section 87 after 213: out of order
- IPC s.88: section 88 after 213: out of order
- IPC s.89: section 89 after 213: out of order
- IPC s.90: section 90 after 213: out of order
- IPC s.91: section 91 after 213: out of order
- IPC s.92: section 92 after 213: out of order
- IPC s.93: section 93 after 213: out of order
- IPC s.94: section 94 after 213: out of order
- IPC s.95: section 95 after 213: out of order
- IPC s.96: section 96 after 213: out of order
- IPC s.97: section 97 after 213: out of order
- IPC s.98: section 98 after 213: out of order
- IPC s.99: section 99 after 213: out of order
- IPC s.100: section 100 after 213: out of order
- IPC s.101: section 101 after 213: out of order
- IPC s.102: section 102 after 213: out of order
- IPC s.103: section 103 after 213: out of order
- IPC s.104: section 104 after 213: out of order
- IPC s.105: section 105 after 213: out of order
- IPC s.106: section 106 after 213: out of order
- IPC s.107: section 107 after 213: out of order
- IPC s.108: section 108 after 213: out of order
- IPC s.109: section 109 after 213: out of order
- IPC s.110: section 110 after 213: out of order
- IPC s.111: section 111 after 213: out of order
- IPC s.112: section 112 after 213: out of order
- IPC s.113: section 113 after 213: out of order
- IPC s.114: section 114 after 213: out of order
- IPC s.115: duplicate section number 115 (cross-reference or schedule?)
- IPC s.115: section 115 after 213: out of order
- IPC s.116: duplicate section number 116 (cross-reference or schedule?)
- IPC s.116: section 116 after 213: out of order
- IPC s.117: section 117 after 213: out of order
- IPC s.118: section 118 after 213: out of order
- IPC s.119: section 119 after 213: out of order
- IPC s.120: section 120 after 213: out of order
- IPC s.122: section 122 after 213: out of order
- IPC s.123: section 123 after 213: out of order
- IPC s.124: section 124 after 213: out of order
- IPC s.125: section 125 after 213: out of order
- IPC s.126: section 126 after 213: out of order
- IPC s.127: section 127 after 213: out of order
- IPC s.128: section 128 after 213: out of order
- IPC s.129: section 129 after 213: out of order
- IPC s.130: section 130 after 213: out of order
- IPC s.131: section 131 after 213: out of order
- IPC s.132: section 132 after 213: out of order
- IPC s.133: section 133 after 213: out of order
- IPC s.134: section 134 after 213: out of order
- IPC s.135: section 135 after 213: out of order
- IPC s.136: section 136 after 213: out of order
- IPC s.137: section 137 after 213: out of order
- IPC s.138: section 138 after 213: out of order
- IPC s.139: section 139 after 213: out of order
- IPC s.140: section 140 after 213: out of order
- IPC s.141: section 141 after 213: out of order
- IPC s.142: section 142 after 213: out of order
- IPC s.143: section 143 after 213: out of order
- IPC s.144: section 144 after 213: out of order
- IPC s.145: section 145 after 213: out of order
- IPC s.146: section 146 after 213: out of order
- IPC s.147: section 147 after 213: out of order
- IPC s.148: section 148 after 213: out of order
- IPC s.149: section 149 after 213: out of order
- IPC s.150: section 150 after 213: out of order
- IPC s.151: section 151 after 213: out of order
- IPC s.152: section 152 after 213: out of order
- IPC s.153: duplicate section number 153 (cross-reference or schedule?)
- IPC s.153: section 153 after 213: out of order
- IPC s.154: section 154 after 213: out of order
- IPC s.155: section 155 after 213: out of order
- IPC s.156: section 156 after 213: out of order
- IPC s.157: section 157 after 213: out of order
- IPC s.158: section 158 after 213: out of order
- IPC s.159: section 159 after 213: out of order
- IPC s.160: section 160 after 213: out of order
- IPC s.166: section 166 after 213: out of order
- IPC s.167: section 167 after 213: out of order
- IPC s.168: section 168 after 213: out of order
- IPC s.169: section 169 after 213: out of order
- IPC s.170: section 170 after 213: out of order
- IPC s.171: section 171 after 213: out of order
- IPC s.172: section 172 after 213: out of order
- IPC s.173: section 173 after 213: out of order
- IPC s.174: section 174 after 213: out of order
- IPC s.175: section 175 after 213: out of order
- IPC s.176: section 176 after 213: out of order
- IPC s.177: section 177 after 213: out of order
- IPC s.178: section 178 after 213: out of order
- IPC s.179: section 179 after 213: out of order
- IPC s.180: section 180 after 213: out of order
- IPC s.181: section 181 after 213: out of order
- IPC s.182: section 182 after 213: out of order
- IPC s.183: section 183 after 213: out of order
- IPC s.184: section 184 after 213: out of order
- IPC s.185: section 185 after 213: out of order
- IPC s.186: section 186 after 213: out of order
- IPC s.187: section 187 after 213: out of order
- IPC s.188: section 188 after 213: out of order
- IPC s.189: section 189 after 213: out of order
- IPC s.190: section 190 after 213: out of order
- IPC s.191: section 191 after 213: out of order
- IPC s.192: section 192 after 213: out of order
- IPC s.193: section 193 after 213: out of order
- IPC s.194: section 194 after 213: out of order
- IPC s.195: section 195 after 213: out of order
- IPC s.196: section 196 after 213: out of order
- IPC s.197: section 197 after 213: out of order
- IPC s.198: section 198 after 213: out of order
- IPC s.199: section 199 after 213: out of order
- IPC s.200: section 200 after 213: out of order
- IPC s.201: duplicate section number 201 (cross-reference or schedule?)
- IPC s.201: section 201 after 213: out of order
- IPC s.202: section 202 after 213: out of order
- IPC s.203: section 203 after 213: out of order
- IPC s.204: section 204 after 213: out of order
- IPC s.205: section 205 after 213: out of order
- IPC s.206: section 206 after 213: out of order
- IPC s.207: section 207 after 213: out of order
- IPC s.208: section 208 after 213: out of order
- IPC s.209: section 209 after 213: out of order

### IEA

- missing section numbers (not found in PDF text): [86, 145, 158, 161]
