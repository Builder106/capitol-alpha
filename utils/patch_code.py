def clean_house_names(name):
    if type(name) is not str:
        return name
    name = name.replace("Hon..", "").replace("Hon.", "").replace("Mrs..", "").replace("Mrs.", "")
    name = name.replace("Mr..", "").replace("Mr.", "").replace("Dr.", "").replace("Dr ", " ")
    name = name.replace("MD", "").replace("FACS", "").replace(",", "").replace('"', '')
    name = " ".join(name.split())
    # Handle "Last First" like "Fields Cleo" or "Newman Marie"
    parts = name.split()
    if len(parts) == 2 and parts[0] in ["Fields", "Newman", "Manning", "Meijer", "Spartz", "Ross"]:
        return f"{parts[1]} {parts[0]}"
        
    return name

names = ['Jefferson Shreve', 'Donald Sternoff Jr. Beyer', 'Patrick Fallon', 'Greg Gianforte', 'Kathy Manning', 'Thomas Suozzi', 'Fields, Cleo', 'Mark Green', 'Tim Moore', 'Sheri Biggs', 'Lisa McClain', 'Kim Schrier', 'Richard W. Allen', 'K. Michael Conaway', 'John W. Rose', 'Susie Lee', 'Earl Leroy Carter', 'Rob Bresnahan', 'Earl Blumenauer', 'Dan Daniel Bishop', 'Nicholas V. Taylor', 'James R. Langevin', 'Scott Scott Franklin', 'Tom Malinowski', 'Christopher L. Jacobs', 'Maria Elvira Salazar', 'Donna Shalala', 'Dean Phillips', 'Meijer, Mr.. Peter', 'Vern Buchanan', 'Lois Frankel', 'Pete Sessions', 'Katherine M. Clark', 'Jonathan Jackson', 'Alan S. Lowenthal', 'Julie Johnson', 'Jared Moskowitz', 'George Whitesides', 'Daniel Meuser', 'Sara Jacobs']

if __name__ == '__main__':
    for n in names:
        print(repr(clean_house_names(n)))
