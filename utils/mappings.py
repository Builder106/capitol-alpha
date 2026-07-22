import pandas as pd

party_map = {
    "A. Mitchell Mcconnell, Jr.": "Republican", "Angus S King, Jr.": "Independent", "Christopher A Coons": "Democrat",
    "Daniel S Sullivan": "Republican", "David A Perdue , Jr": "Republican", "Gary C Peters": "Democrat",
    "Jacklyn S Rosen": "Democrat", "James M Inhofe": "Republican", "Jerry Moran,": "Republican",
    "John Hoeven": "Republican", "Kelly Loeffler": "Republican", "Mark R Warner": "Democrat",
    "Michael F Bennet": "Democrat", "Pat Roberts": "Republican", "Patrick J Toomey": "Republican",
    "Rick Scott": "Republican", "Ron Johnson": "Republican", "Ron L Wyden": "Democrat",
    "Sheldon Whitehouse": "Democrat", "Shelley M Capito": "Republican", "Susan M Collins": "Republican",
    "Thomas R Carper": "Democrat", "Tina Smith": "Democrat", "William Cassidy": "Republican",
    "Josh Gottheimer": "Democrat", "Darrell E. Issa": "Republican", "Nancy Pelosi": "Democrat",
    "Suzan K. DelBene": "Democrat", "Mark Dr Green": "Republican", "Kevin Hern": "Republican",
    "Scott H. Peters": "Democrat", "David Trone": "Democrat", "Daniel Goldman": "Democrat",
    "Marie Newman": "Democrat", "Carol Devine Miller": "Republican", "Marjorie Taylor Greene": "Republican",
    "Marjorie Taylor Mrs Greene": "Republican", "Michael Thomas McCaul": "Republican", "Virginia Foxx": "Republican",
    "Gilbert Cisneros": "Democrat", "Marie Gluesenkamp Perez": "Democrat", "Ro Khanna": "Democrat",
    
    "Jefferson Shreve": "Republican",
    "Donald Sternoff Jr. Beyer": "Democrat",
    "Patrick Fallon": "Republican",
    "Greg Gianforte": "Republican",
    "Kathy Manning": "Democrat",
    "Thomas Suozzi": "Democrat",
    "Cleo Fields": "Democrat",
    "Mark Green": "Republican",
    "Tim Moore": "Republican",
    "Sheri Biggs": "Republican",
    "Lisa McClain": "Republican",
    "Kim Schrier": "Democrat",
    "Richard W. Allen": "Republican",
    "K. Michael Conaway": "Republican",
    "John W. Rose": "Republican",
    "Susie Lee": "Democrat",
    "Earl Leroy Carter": "Republican",
    "Rob Bresnahan": "Republican",
    "Earl Blumenauer": "Democrat",
    "Dan Daniel Bishop": "Republican",
    "Nicholas V. Taylor": "Republican",
    "James R. Langevin": "Democrat",
    "Scott Scott Franklin": "Republican",
    "Tom Malinowski": "Democrat",
    "Christopher L. Jacobs": "Republican",
    "Maria Elvira Salazar": "Republican",
    "Donna Shalala": "Democrat",
    "Dean Phillips": "Democrat",
    "Peter Meijer": "Republican",
    "Vern Buchanan": "Republican",
    "Lois Frankel": "Democrat",
    "Pete Sessions": "Republican",
    "Katherine M. Clark": "Democrat",
    "Jonathan Jackson": "Democrat",
    "Alan S. Lowenthal": "Democrat",
    "Julie Johnson": "Democrat",
    "Jared Moskowitz": "Democrat",
    "George Whitesides": "Democrat",
    "Daniel Meuser": "Republican",
    "Sara Jacobs": "Democrat",
    "C. Scott Franklin": "Republican",
    "Valerie Hoyle": "Democrat",
    "Kelly Louise Morrison": "Democrat",
    "Brad Sherman": "Democrat",
    "Greg Landsman": "Democrat",
    "John Curtis": "Republican",
    "Kim Dr Schrier": "Democrat",
    "Mike Kelly": "Republican",
    "Zoe Lofgren": "Democrat",
    "William R. Keating": "Democrat",
    "James French Hill": "Republican",
    "Nicholas Van Taylor": "Republican",
    "David B. McKinley": "Republican",
    "John James": "Republican",
    "Michael C. Burgess": "Republican",
    "Mikie Sherrill": "Democrat",
    "Donald Sternoff Honorable Jr. Beyer": "Democrat",
    "April McClain Delaney": "Democrat",
    "Neal Patrick MD, Facs Dunn": "Republican",
    "Julia Letlow": "Republican",
    "Bruce Westerman": "Republican",
    "Bradley S. Schneider": "Democrat",
    "Donald Sternoff Jr.. Beyer": "Democrat",
    "Blake Moore": "Republican",
    "John A. Yarmuth": "Democrat",
    "Steve Cohen": "Democrat",
    "Joe Courtney": "Democrat",
    "Michael Patrick Guest": "Republican",
    "Michael Waltz": "Republican",
    "David P. Joyce": "Republican",
    "Michael Garcia": "Republican",
    "Robert J. Wittman": "Republican",
    "Cindy Axne": "Democrat",
    "David J. Taylor": "Republican",
    "Dan Newhouse": "Republican",
    "Greg Stanton": "Democrat",
    "Scott Mr Franklin": "Republican",
    "Brian Mast": "Republican",
    "Thomas H. Jr. Kean": "Republican",
    "Brandon Gill": "Republican",
    "John Rutherford": "Republican",
    "Shri Thanedar": "Democrat",
    "Byron Donalds": "Republican",
    "Victoria Spartz": "Republican",
    "Ritchie John Torres": "Democrat",
    "Chellie Pingree": "Democrat",
    "Austin Scott": "Republican",
    "Debbie Dingell": "Democrat",
    "Dwight Evans": "Democrat",
    "Ashley Hinson Arenholz": "Republican",
    "David Madison Cawthorn": "Republican",
    "Carolyn B. Maloney": "Democrat",
    "Chip Roy": "Republican",
    "Elaine Luria": "Democrat",
    "Scott Franklin": "Republican",
    "Judy Chu": "Democrat",
    "Ann Wagner": "Republican",
    "Lloyd Doggett": "Democrat",
    "Thomas H. Kean": "Republican",
    "Mo Brooks": "Republican",
    "Laurel Lee": "Republican",
    "Michael John Gallagher": "Republican",
    "Peter Welch": "Democrat",
    "Rick Larsen": "Democrat",
    "Richard Dean Dr McCormick": "Republican",
    "Michael K. Simpson": "Republican",
    "Gerald E. Connolly": "Democrat",
    "John B. Larson": "Democrat",
    "Rudy III. Yakym": "Republican",
    "Ed Perlmutter": "Democrat",
    "Deborah K. Ross": "Democrat",
    "Neal Patrick Dunn MD, FACS": "Republican",
    "Harley E. Jr.. Rouda": "Democrat",
    "Susan A. Davis": "Democrat",
    "Bob Gibbs": "Republican",
    "Thomas H. Jr.. Kean": "Republican",
    "Kathy Castor": "Democrat",
    "James Comer": "Republican",
    "Doris O. Matsui": "Democrat",
    "Bill Flores": "Republican",
    "Anna Paulina Luna": "Republican",
    "Michael A. Collins": "Republican",
    "Max Miller": "Republican",
    "Sean Casten": "Democrat",
    "James E Hon Banks": "Republican",
    "Cheri Bustos": "Democrat",
    "Debbie Wasserman Schultz": "Democrat",
    "Ed Case": "Democrat",
    "August Lee II. Pfluger": "Republican",
    "Lloyd K. Smucker": "Republican",
    "Stephen F. Lynch": "Democrat",
    "Joseph D. Morelle": "Democrat",
    "Daniel Crenshaw": "Republican",
    "Eleanor Holmes Norton": "Democrat",
    "Roger W. Marshall": "Republican",
    "Adam Kinzinger": "Republican",
    "Robert C. \"Bobby\" Scott": "Democrat",
    "James E. Banks": "Republican",
    "Roger Williams": "Republican",
    "Neal Patrick MD, FACS Dunn": "Republican",
    "Seth Moulton": "Democrat",
    "Ron Estes": "Republican",
    "William R. IV. Timmons": "Republican",
    "Morgan McGarvey": "Democrat",
    "Warren Davidson": "Republican",
    "Frank Jr.. Pallone": "Democrat",
    "Tom Rice": "Republican",
    "Neal Patrick Dunn, MD, FACS": "Republican",
    "Adam Smith": "Democrat",
    "Andrew Garbarino": "Republican",
    "Susan W. Brooks": "Republican",
    "Mary Gay Scanlon": "Democrat",
    "Thomas R. Suozzi": "Democrat",
    "Anthony E. Gonzalez": "Republican",
    "Brian Babin": "Republican",
    "Michael A. Jr. Collins": "Republican",
    "Emily Randall": "Democrat",
    "Stephanie Bice": "Republican",
    "Scott DesJarlais": "Republican",
    "Laurel Mrs Lee": "Republican",
    "Brian Higgins": "Democrat",
    "Cathy McMorris Rodgers": "Republican",
    "Mark Pocan": "Democrat",
    "Matt Gaetz": "Republican",
    "Ruben Gallego": "Democrat",
    "Bill Jr.. Pascrell": "Democrat",
    "Mark Alford": "Republican",
    "Greg Steube": "Republican",
    "David Cheston Rouzer": "Republican",
    "Sean Patrick Maloney": "Democrat",
    "John McGuire": "Republican",
    "David E. Price": "Democrat",
    "Garret Graves": "Republican",
    "Nanette Barragan": "Democrat",
    "Glenn S. Grothman": "Republican",
    "Raúl M. Grijalva": "Democrat",
    "Felix Barry Moore": "Republican",
    "John Garamendi": "Democrat",
    "Tom O'Halleran": "Democrat",
    "Guy Mr Reschenthaler": "Republican",
    "Linda T. Sanchez": "Democrat",
    "Lance Gooden": "Republican",
    "Hakeem S. Jeffries": "Democrat",
    "Justin Amash": "Libertarian",
    "Brad Knott": "Republican",
    "Brandon McDonald Williams": "Republican",
    "Deborah Ross": "Democrat",
    "Laura Friedman": "Democrat",
    "Jeff Jackson": "Democrat",
    "Terri A. Sewell": "Democrat",
    "Cliff Bentz": "Republican",
    "Adrian Smith": "Republican",
    "Dave Min": "Democrat",
    "Jeff Duncan": "Republican",
    "David Kustoff": "Republican"
}

def clean_house_names(name):
    if type(name) is not str:
        return name
    name = str(name).strip()
    
    if ', Hon..' in name:
        parts = name.split(', Hon..')
        name = f"{parts[1].strip()} {parts[0].strip()}"
    elif ', Hon.' in name:
        parts = name.split(', Hon.')
        name = f"{parts[1].strip()} {parts[0].strip()}"
        
    name = name.replace("Hon..", "").replace("Hon.", "").replace("Mrs..", "").replace("Mrs.", "")
    name = name.replace("Mr..", "").replace("Mr.", "").replace("Dr.", "").replace("Dr ", " ")
    name = name.replace("MD", "").replace("FACS", "").replace(",", "").replace('"', '')
    name = " ".join(name.split())
    
    # Handle "Last First" like "Fields Cleo" or "Newman Marie"
    parts = name.split()
    if len(parts) == 2 and parts[0] in ["Fields", "Newman", "Manning", "Meijer", "Spartz", "Ross"]:
        name = f"{parts[1]} {parts[0]}"
        
    return name

def update_flourish_export(filepath='data/flourish_racing_bar_export.csv'):
    df = pd.read_csv(filepath)
    for col in df.columns:
        if col.strip() == 'legislator_name':
            df.rename(columns={col: 'legislator_name'}, inplace=True)
        if col.strip() == 'Party':
            df.rename(columns={col: 'Party'}, inplace=True)

    df['legislator_name'] = df['legislator_name'].apply(clean_house_names)
    df['Party'] = df['legislator_name'].map(party_map).fillna('Unknown')
    df.to_csv(filepath, index=False)

    missing = df[df['Party'] == 'Unknown'].copy()
    if len(missing.columns) > 2:
        missing['MaxVol'] = missing.iloc[:, 2:].max(axis=1)
        names = missing.sort_values('MaxVol', ascending=False)['legislator_name'].tolist()
    else:
        names = missing['legislator_name'].tolist()
    print(f"Remaining Unknowns: {len(names)}")
    print(names[:10])
    return df, names

if __name__ == '__main__':
    update_flourish_export()

