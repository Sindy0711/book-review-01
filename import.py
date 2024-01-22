import os,csv

from sqlalchemy import create_engine , text
from sqlalchemy.orm import scoped_session, sessionmaker

engine = create_engine("postgresql://postgres:123456@localhost:5432/postgres")
db = scoped_session(sessionmaker(bind=engine))


def main():
    f = open("books.csv", "r")  # needs to be opened during reading csv
    reader = csv.reader(f)
    next(reader)
    for isbn, title, author, year in reader:
        db.execute(
            text("INSERT INTO books (isbn, title, author, year) VALUES (:isbn, :title, :author, :year)"),
               {"isbn": isbn, "title": title, "author": author, "year": year})
        db.commit()
        print(f"Added book with ISBN: {isbn} Title: {title}  Author: {author}  Year: {year}")


if __name__ == '__main__':
    main()
