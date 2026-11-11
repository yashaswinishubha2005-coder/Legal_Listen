"""Acts expected in data/raw/acts/. Effective dates and URLs are placeholders, TO_VERIFY."""

from lexvaani.schemas.corpus import ActInfo

ACTS: list[ActInfo] = [
    ActInfo(code="BNS", title="Bharatiya Nyaya Sanhita", year=2023, effective_from="2024-07-01", file_glob="*nyaya*"),
    ActInfo(code="BNSS", title="Bharatiya Nagarik Suraksha Sanhita", year=2023, effective_from="2024-07-01", file_glob="*nagarik*"),
    ActInfo(code="BSA", title="Bharatiya Sakshya Adhiniyam", year=2023, effective_from="2024-07-01", file_glob="*sakshya*"),
    ActInfo(code="ITA", title="Information Technology Act", year=2000, file_glob="*information*technology*"),
    ActInfo(code="CPA", title="Consumer Protection Act", year=2019, file_glob="*consumer*"),
    ActInfo(code="HMA", title="Hindu Marriage Act", year=1955, file_glob="*hindu*marriage*"),
    ActInfo(code="HSA", title="Hindu Succession Act", year=1956, file_glob="*hindu*succession*"),
    ActInfo(code="SMA", title="Special Marriage Act", year=1954, file_glob="*special*marriage*"),
    ActInfo(code="PWDV", title="Protection of Women from Domestic Violence Act", year=2005, file_glob="*domestic*violence*"),
    ActInfo(code="DPA", title="Dowry Prohibition Act", year=1961, file_glob="*dowry*"),
    ActInfo(code="GWA", title="Guardians and Wards Act", year=1890, file_glob="*guardian*"),
    ActInfo(code="TPA", title="Transfer of Property Act", year=1882, file_glob="*transfer*property*"),
    ActInfo(code="RA", title="Registration Act", year=1908, file_glob="*registration*"),
    ActInfo(code="SRA", title="Specific Relief Act", year=1963, file_glob="*specific*relief*"),
    ActInfo(code="LIMA", title="Limitation Act", year=1963, file_glob="*limitation*"),
    ActInfo(code="KLRA", title="Karnataka Land Revenue Act", year=1964, jurisdiction="IN-KA", file_glob="*land*revenue*"),
    # Not in the requested list, but referenced for pre-2024-07-01 incidents (old regime). Add their PDFs.
    ActInfo(code="IPC", title="Indian Penal Code", year=1860, file_glob="*penal*code*"),
    ActInfo(code="CrPC", title="Code of Criminal Procedure", year=1973, file_glob="*criminal*procedure*"),
    ActInfo(code="IEA", title="Indian Evidence Act", year=1872, file_glob="*evidence*act*"),
]
BY_CODE = {a.code: a for a in ACTS}
