# -*- coding: utf-8 -*-
from . import fields
from typing import overload, Any, Iterable
from psycopg2 import sql
import psycopg2
import logging

logger = logging.getLogger(__name__)


class MetaModel(type):
    def __new__(cls, name : str, bases : tuple, dct : dict):
        """For each model which inherits a class with MetaModel as its metaclass, adds the elements of the parent classes to __dict__"""
        for base in bases:
            for name, prop in base.__dict__.items():
                if name not in dct:
                    dct[name] = prop
        return super().__new__(cls, name, bases, dct)


class Model(metaclass=MetaModel):
    _table: str
    _fields: dict[str, fields.Field]
    _sql_constraints: list[tuple[str, str]]

    id = fields.ID()

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = #
    #                                   INSTANCE INITIALIZATION                                   #
    #                              Initiate an instance of this model                             #
    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = #
    def __init__(self, values : dict[str, Any] = {}):
        """Create instance of Model given values for the fields.
        For fields that are not in values, we initiate them with Field.get_default().

        :param values: Dictionary of field name and field value to instanciate the class with."""
        # Configure _fields attribute
        self._fields = self._get_fields()

        # Validate if all values are in fact fields of this model
        _fields = self._fields
        _fields_nok = [field for field in values if field not in _fields]
        if _fields_nok:
            plural = "s" if len(_fields_nok) != 1 else ""
            raise ValueError(f"Invalid field{plural} for model {self.__class__.__name__}")

        # Set fields that are not present in values
        self.set_fields_defaults([field for field in _fields if field not in values])

        # Set fields present in values
        self.set_fields(values)

    def _get_fields(self) -> dict[str, fields.Field]:
        """Get mapping of field_name -> Field"""
        fields_dict = self.__class__.__dict__
        _fields = {
            field: value for field, value in fields_dict.items()
            if (field != "id" and
                field[:1] != "_" and
                not callable(value) and
                not isinstance(value, classmethod))
        }
        return {"id": fields_dict["id"], **_fields}

    def set_fields(self, values : dict[str, Any] = {}):
        """Set this instance's fields given the field name -> field value dictionary in values"""
        for field, value in values.items():
            self[field] = value

    def set_fields_defaults(self, fields_list : Iterable[str]):
        """Set this instance's fields with their default values given a list of fields to default"""
        _fields = self._fields
        for field in fields_list:
            self[field] = _fields[field].get_default()

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = #
    #                                    DATABASE CONFIGURATION                                   #
    #                   Configure the database table and columns for this model                   #
    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = #
    def configure_table(self, cr : psycopg2.extensions.cursor):
        """Configure database table for a class inheriting Model.
        - Create database if it doesn't exist;
        - Create columns present in code but not yet in database;
        - Delete coluns not present in code but in the database."""
        table_name = self._table
        query_table = sql.SQL("CREATE TABLE IF NOT EXISTS {table} ()").format(table=sql.Identifier(table_name))
        try:
            cr.execute(query_table)
        except Exception as e:
            logger.exception(f"Error attempting to create table {table_name}")
            raise e

        _fields = self._fields
        _fields_existing = self._get_current_columns(cr)
        _fields_create = {name: field for name, field in _fields.items() if name not in _fields_existing}
        _fields_delete = [field for field in _fields_existing if field not in _fields]

        column_query_list = [field.get_creation_query(name) for name, field in _fields_create.items()]
        column_query_list += [sql.SQL("DROP COLUMN IF EXISTS {field}").format(field=sql.Composable(field)) for field in _fields_delete]
        column_query = sql.SQL("ALTER TABLE {table}\n{columns}").format(
            table=sql.Identifier(table_name),
            columns=sql.SQL(",\n").join(column_query_list),
        )

        try:
            if column_query_list:
                cr.execute(column_query)
            cr.connection.commit()
        except Exception as e:
            logger.exception(f"Error attempting to configure table {table_name}")
            raise e

        logger.info(f"Configured table {table_name}")

    def _get_current_columns(self, cr : psycopg2.extensions.cursor) -> list[str]:
        """Get list of columns present in this model's database"""
        cr.execute(sql.SQL("SELECT * FROM {table} LIMIT 0").format(table=sql.Identifier(self._table)))
        return [col[0] for col in cr.description]

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = #
    #                                         CRUD METHODS                                        #
    #                             CRUD = Create, Read, Update, Delete                             #
    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    #                                            CREATE                                           #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    @overload
    def create(self, cr : psycopg2.extensions.cursor, values : dict[str, Any]) -> "Model":
        """Create a record of this Model, inserting it in the database and returning a class instance"""
        ...

    @overload
    def create(self, cr : psycopg2.extensions.cursor, values : Iterable[dict[str, Any]]) -> list["Model"]:
        """Create multiple records of this Model, inserting them in the database and returning a list of class instances"""
        ...

    def create(self, cr : psycopg2.extensions.cursor, values):
        """Create one or more records of this Model, inserting them in the database and returning class instance(s)"""
        if isinstance(values, dict):
            return self._create(cr, values)
        if isinstance(values, Iterable):
            output = []
            for value in values:
                obj = self._create(cr, value)
                output.append(obj)
            return output
        raise ValueError("The values argument must be either a dictionary or an Iterable of dictionaries")

    def _create(self, cr : psycopg2.extensions.cursor, values : dict[str, Any]) -> "Model":
        """Internal implementation of create()"""
        if "id" in values:
            values.pop("id")

        _fields = self._fields
        columns = []
        values_sql = []
        for fname, value in values.items():
            field = _fields[fname]
            columns.append(fname)
            values_sql.append(field.value_to_column(value))

        query = sql.SQL(
            "INSERT INTO {table} ({columns}) "
            "VALUES ({values}) "
            "RETURNING id"
        ).format(
            table=sql.Identifier(self._table),
            columns=sql.SQL(", ").join(map(sql.Identifier, columns)),
            values=sql.SQL(", ").join(map(sql.Literal, values_sql)),
        )
        cr.execute(query)
        _id, = cr.fetchone()
        logger.info(f"Create {self._table}, id = {_id}, success")
        return self.read(cr, _id)

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    #                                             READ                                            #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    @overload
    def read(self, cr : psycopg2.extensions.cursor, _id : int, fields_list : Iterable[str] = []) -> "Model":
        """Fetch one row from this model's table"""
        ...

    @overload
    def read(self, cr : psycopg2.extensions.cursor, _id : Iterable[int], fields_list : Iterable[str] = []) -> list["Model"]:
        """Fetch multiple rows from this model's table"""
        ...

    def read(self, cr : psycopg2.extensions.cursor, _id, fields_list : Iterable[str] = []):
        """Fetch one or more rows from this model's table"""
        # _id validation
        if not isinstance(_id, (int, Iterable)):
            raise ValueError("The ID must be either an integer or an Iterable of integers")
        if isinstance(_id, int) and _id < 1:
            raise ValueError("The ID must be a strictly positive integer")
        if isinstance(_id, Iterable) and any(not isinstance(__id, int) or __id < 1 for __id in _id):
            raise ValueError("The IDs must be strictly positive integers")

        # If no fields were received, fetch everything
        if not fields_list:
            fields_list = self._fields
        # Ensure we always fetch the id too
        elif "id" not in fields_list:
            fields_list = ["id", *fields_list]

        single_mode = isinstance(_id, int)

        # Construct WHERE clause
        if single_mode:
            where_clause = f"id = {_id}"
        else:
            _ids = ", ".join(str(__id) for __id in _id)
            where_clause = f"id in ({_ids})"

        query = sql.SQL(
            "SELECT {columns} "
            "FROM {table} "
            "WHERE {where}"
        ).format(
            columns=sql.SQL(", ").join(map(sql.Identifier, fields_list)),
            table=sql.Identifier(self._table),
            where=sql.SQL(where_clause),
        )
        cr.execute(query)
        header = cr.description

        if single_mode:
            row = cr.fetchone()
            values = self._row_to_dict(header, row)
            logger.info(f"Read {self._table}, id = {_id}, success")
            return self.__class__(values)

        else:
            output = []
            output_ids = []
            rows = cr.fetchall()
            for row in rows:
                values = self._row_to_dict(header, row)
                output.append(self.__class__(values))
                output_ids.append(values["id"])
            output_ids_str = ", ".join(map(str, output_ids))
            logger.info(f"Read {self._table}, id in ({output_ids_str}), success")
            return output

    def _row_to_dict(self, header : list[psycopg2.extensions.Column], row : tuple[Any]) -> dict[str, Any]:
        """Convert a row received from the database into a field name -> field value dictionary"""
        if not row:
            return {}
        return {d.name: row[i] for i, d in enumerate(header)}

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    #                                            UPDATE                                           #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    def update(self, cr : psycopg2.extensions.cursor, values : dict[str, Any]) -> bool:
        """Write the given values into the database record of this instance's id and update the instance"""
        if "id" in values:
            values.pop("id")

        _fields = self._fields
        set_clauses = []
        for fname, value in values.items():
            field = _fields[fname]
            set_clauses.append(sql.SQL("{column} = {value}").format(
                column=sql.Identifier(fname),
                value=sql.Literal(field.value_to_column(value)),
            ))
        where_clause = sql.SQL("{column} = {value}").format(
            column=sql.Identifier("id"),
            value=sql.Literal(self.id),
        )

        query = sql.SQL(
            "UPDATE {table} "
            "SET {set_clause} "
            "WHERE {where}"
        ).format(
            table=sql.Identifier(self._table),
            set_clause=sql.SQL(", ").join(set_clauses),
            where=where_clause,
        )
        cr.execute(query)
        cr.connection.commit()

        num_rows = cr.rowcount
        if num_rows == 0:
            logger.warning(f"Update {self._table}, id = {self.id}, rowcount = 0")
            return False
        self.set_fields(values)
        logger.info(f"Update {self._table}, id = {self.id}, success")
        return True

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    #                                            DELETE                                           #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    def delete(self, cr : psycopg2.extensions.cursor) -> bool:
        """Delete the database record associated to this instance"""
        _id = self.id
        where_clause = sql.SQL("{column} = {value}").format(
            column=sql.Identifier("id"),
            value=sql.Literal(_id),
        )
        query = sql.SQL(
            "DELETE FROM {table} "
            "WHERE {where}"
        ).format(
            table=sql.Identifier(self._table),
            where=where_clause,
        )
        cr.execute(query)
        cr.connection.commit()

        num_rows = cr.rowcount
        if num_rows == 0:
            logger.warning(f"Delete {self._table}, id = {_id}, rowcount = 0")
            return False
        self.set_fields_defaults(self._fields.keys())
        logger.info(f"Delete {self._table}, id = {_id}, success")
        return True

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = #
    #                                        USEFUL METHODS                                       #
    #  #
    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = #
    def search(self, cr : psycopg2.extensions.cursor, domain : list[str | list], limit : int = 0) -> list["Model"]:
        """Search for database records fitting the provided conditions

        :param domain: List of conditions to search the records for; for more details, see `_domain_to_sql()`.
        :param limit: Number of records to fetch; if zero or below, fetch all matching records.
        :return: List of Model instances """
        where_clause = self._domain_to_sql(domain)
        limit_clause = sql.SQL("")
        if limit > 0:
            limit_clause = sql.SQL("LIMIT {limit}").format(limit=sql.Literal(limit))

        query = sql.SQL(
            "SELECT {columns} "
            "FROM {table} "
            "WHERE {where} "
            "{limit}"
        ).format(
            columns=sql.Identifier("id"),
            table=sql.Identifier(self._table),
            where=where_clause,
            limit=limit_clause,
        )
        cr.execute(query)
        rows = cr.fetchall()
        if not rows:
            return [self.__class__()]
        ids = [row[0] for row in rows]
        return self.read(cr, ids)

    def _domain_to_sql(self, domain : list[str | list | tuple]) -> sql.SQL:
        """"""
        if not domain:
            return sql.Literal(True)

        output = sql.SQL("")
        operator = False

        for node in domain:
            if isinstance(node, str) and len(node) == 1:
                if not operator:
                    raise ValueError(f"Invalid domain {domain!r}")
                match node:
                    case "&":
                        output += sql.SQL(" AND ")
                    case "|":
                        output += sql.SQL(" OR ")
                    case _:
                        raise ValueError(f"Invalid domain node {node!r}")
                operator = False

            elif isinstance(node, (list, tuple)) and len(node) == 3:
                if operator:
                    raise ValueError(f"Invalid domain {domain!r}")
                output += sql.SQL(" ").join((
                    sql.Identifier(node[0]),
                    sql.SQL(node[1]),
                    sql.Literal(node[2]),
                ))
                operator = True

            else:
                raise ValueError(f"Invalid domain node {node!r}")

        if not operator:
            raise ValueError(f"Invalid domain {domain!r}")

        return output


    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = #
    #                                        DUNDER METHODS                                       #
    #                   Methods for basic Python operations between class instances               #
    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = #
    def asdict(self) -> dict[str, Any]:
        return {field: self[field] for field in self._fields}

    def __getitem__(self, field : str) -> Any:
        return getattr(self, field)

    def __setitem__(self, field : str, value : Any):
        return setattr(self, field, value)

    def __repr__(self) -> str:
        return f"{self._table}({self.id or ''})"


def configure_models(cr : psycopg2.extensions.cursor) -> dict[str, Model]:
    """Gather all classes inheriting from Model and configure the database for them,
    returning a _table -> instance dictionary for future use"""
    output = {}
    for _class in Model.__subclasses__():
        instance = _class()
        instance.configure_table(cr)
        output[instance._table] = instance
    return output
