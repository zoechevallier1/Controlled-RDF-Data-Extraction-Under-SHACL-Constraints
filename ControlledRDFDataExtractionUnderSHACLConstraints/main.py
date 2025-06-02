from rdflib import Graph, URIRef, BNode
import time
import statistics
import argparse

# Function to resolve constraints for Property Shapes
def property_shape_resolution(targetSchema, PS, Prop_m, Prop_o):
    queryTargetedProperty =  f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    SELECT distinct ?p WHERE {{ {format_resource(PS)} sh:path ?p }}
    """

    results = execute_query(queryTargetedProperty, targetSchema)
    p = next((str(r[0]) for r in results if r), "")

    
    queryConstraints =  f"""
       PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
       PREFIX sh: <http://www.w3.org/ns/shacl#>
       SELECT distinct ?prop_sh ?value WHERE {{ {format_resource(PS)} ?prop_sh ?value }}
       """

    constraints = execute_query(queryConstraints, targetSchema)
    parts = []

    for prop_sh, value in constraints:
        if str(prop_sh) in ["http://www.w3.org/ns/shacl#and", "http://www.w3.org/ns/shacl#or"]:
            operator = "&&" if prop_sh.endswith("and") else "||"
            logical_parts = []
            queryEltList = f"""
                SELECT distinct ?elt WHERE {{
                    {format_resource(value)} rdf:rest*/rdf:first ?elt .
                }}
                """
            sameElts = []
            for row in execute_query(queryEltList, targetSchema):
                queryCst = f"""
                SELECT distinct ?prop ?val WHERE {{
                    {format_resource(row[0])} ?prop ?val.
                }}
                """
                part_elt = []
                for prop, val in execute_query(queryCst, targetSchema):
                    part_elt.append(f"({basic_constraint_resolution(p, str(prop), str(val), Prop_m, Prop_o)})")         
                logical_parts.append(f"({' && '.join(p for p in part_elt if p)})" if any(part_elt) else "")
            if logical_parts:
                parts.append(f"({' {} '.format(operator).join(p for p in logical_parts if p)})")
            
        elif str(prop_sh) == "http://www.w3.org/ns/shacl#xone":
            logical_parts = []
            queryEltList = f"""
                SELECT distinct ?elt WHERE {{
                    {format_resource(value)} rdf:rest*/rdf:first ?elt .
                }}
                """
            sameElts = []
            for row in execute_query(queryEltList, targetSchema):
                queryCst = f"""
                SELECT distinct ?prop ?val WHERE {{
                    {format_resource(row[0])} ?prop ?val.
                }}
                """
                part_elt = []
                for prop, val in execute_query(queryCst, targetSchema):
                    part_elt.append(f"({basic_constraint_resolution(p, str(prop), str(val), Prop_m, Prop_o)})")         
                logical_parts.append(f"({' && '.join(p for p in part_elt if p)})" if any(part_elt) else "")

            xone_parts = []
            for i in range(len(logical_parts)):
                inner_parts = []
                for j, c in enumerate(logical_parts):
                    if c: 
                        if i == j:
                            inner_parts.append(f"({c})")
                        else:
                            inner_parts.append(f"!({c})")
                if inner_parts:  
                    xone_parts.append(" && ".join(inner_parts))
            
            if xone_parts:  
                parts.append(f"({' || '.join(f'({part})' for part in xone_parts if part)})")


        elif str(prop_sh) == "http://www.w3.org/ns/shacl#not":
            queryNot = f"""
            SELECT distinct ?prop_sh ?k_sh WHERE {{
                {format_resource(value)} ?prop_sh ?k_sh
            }}
            """
            not_parts = []
            for prop_sh, k_sh in execute_query(queryNot, targetSchema):
                not_parts.append(f"({basic_constraint_resolution(p, str(prop_sh), str(k_sh), Prop_m, Prop_o)})")
            if not_parts:
                parts.append(f"!({' && '.join(p for p in not_parts if p)})"  )
        else:
            parts.append(basic_constraint_resolution(p, prop_sh, value, Prop_m, Prop_o))  
    
    return f"({' && '.join([p for p in parts if p])})" if any(parts) else ""

# Function to resolve constraints for Node Shapes
def node_shape_resolution(targetSchema, NS, Prop_m, Prop_o):

    parts = []
    queryPropertyShapes = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    SELECT distinct ?ps ?prop WHERE {{ {format_resource(NS)} sh:property ?ps . ?ps sh:path ?prop. }}
    """
    for row in execute_query(queryPropertyShapes, targetSchema):
        ps_resolution = property_shape_resolution(targetSchema, row[0], Prop_m, Prop_o)
        if ps_resolution:
            parts.append(ps_resolution)

    queryConstraints =  f"""
       PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
       PREFIX sh: <http://www.w3.org/ns/shacl#>
       SELECT distinct ?prop_sh ?value ?elt WHERE {{ {format_resource(NS)} ?prop_sh ?value. }}
       """


    constraints = execute_query(queryConstraints, targetSchema)

    for prop_sh, value, elt in constraints:
        if str(prop_sh) in ["http://www.w3.org/ns/shacl#and", "http://www.w3.org/ns/shacl#or"]:
            operator = "&&" if prop_sh.endswith("and") else "||"
            logical_parts = []
            queryEltList = f"""
                SELECT distinct ?elt ?typeShape WHERE {{
                    {format_resource(value)} rdf:rest*/rdf:first ?elt . ?elt rdf:type ?typeShape.
                }}
                """
            for row in execute_query(queryEltList, targetSchema):
                if str(row[1]) == "http://www.w3.org/ns/shacl#NodeShape":
                    logical_parts.append(f"({node_shape_resolution(targetSchema, row[0], Prop_m, Prop_o)})")
                elif str(row[1]) == "http://www.w3.org/ns/shacl#PropertyShape":
                    logical_parts.append(f"({property_shape_resolution(targetSchema, row[0], Prop_m, Prop_o)})")
            if logical_parts:
                parts.append(f"({' {} '.format(operator).join(p for p in logical_parts if p)})")
            
        elif str(prop_sh) == "http://www.w3.org/ns/shacl#xone":
            logical_parts = []
            queryEltList = f"""
                SELECT distinct ?elt ?typeShape WHERE {{
                    {format_resource(value)} rdf:rest*/rdf:first ?elt . ?elt rdf:type ?typeShape.
                }}
                """
            for row in execute_query(queryEltList, targetSchema):
                if str(row[1]) == "http://www.w3.org/ns/shacl#NodeShape":
                    logical_parts.append(f"({node_shape_resolution(targetSchema, row[0], Prop_m, Prop_o)})")
                elif str(row[1]) == "http://www.w3.org/ns/shacl#PropertyShape":
                    logical_parts.append(f"({property_shape_resolution(targetSchema, row[0], Prop_m, Prop_o)})")

            xone_parts = []
            for i in range(len(logical_parts)):
                inner_parts = []
                for j, c in enumerate(logical_parts):
                    if c:  
                        if i == j:
                            inner_parts.append(f"({c})")
                        else:
                            inner_parts.append(f"!({c})")
                if inner_parts:  
                    xone_parts.append(" && ".join(inner_parts))
            
            if xone_parts: 
                parts.append(f"({' || '.join(f'({part})' for part in xone_parts if part)})")


        elif str(prop_sh) == "http://www.w3.org/ns/shacl#not":
            queryNot = f"""
            SELECT ?typeShape WHERE {{
                {format_resource(liste)} rdf:type ?typeShape
            }}
            """
            not_parts = []
            for r in execute_query(queryNot, targetSchema, cache):
                if str(r[0]) == "http://www.w3.org/ns/shacl#NodeShape":
                    not_parts.append(f"!({node_shape_resolution(targetSchema, liste, Prop_m, Prop_o, cache)})")
                elif str(r[0]) == "http://www.w3.org/ns/shacl#PropertyShape":
                    not_parts.append(f"!({property_shape_resolution(targetSchema, liste, Prop_m, Prop_o, cache)})")
            if not_parts:
                parts.append(f"({' && '.join(p for p in not_parts if p)})")

    return f"({' && '.join(p for p in parts if p)})" if any(parts) else ""
            


def generate_extraction_query(targetSchema, C, Prop_m, Prop_o):
    """
    Principal Function to generate the SPARQL extraction query.
    Combines the CONSTRUCT section, the WHERE clause, and constraints from
    NodeShapes and PropertyShapes.
    :param targetSchema: The RDF graph containing the SHACL shapes.
    :param C: The target class for which the extraction is performed.
    :param Prop_m: Mandatory properties to extract.
    :param Prop_o: Optional properties to extract.
    :return: A SPARQL CONSTRUCT query string.
    """
    parts = []
    # Namespace declarations & CONSTRUCT clause
    parts.append("PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>")
    parts.append("PREFIX sh: <http://www.w3.org/ns/shacl#>")
    parts.append(f"CONSTRUCT {{ ?e rdf:type <{C}> .")
    for p in Prop_m + Prop_o:
        prop = p.split('#')[1] if '#' in p else p.split('/')[-1]
        parts.append(f"?e <{p}> ?o_{prop} .")
    parts.append("}")
    
    # Clause WHERE
    parts.append("WHERE {")
    for p in Prop_m:
        prop = p.split('#')[1] if '#' in p else p.split('/')[-1]
        parts.append(f"?e <{p}> ?o_{prop} .")
        parts.append(f"{{ SELECT ?e (COUNT(?o_{prop}) AS ?{prop}Count) WHERE {{ ?e <{p}> ?o_{prop} }} GROUP BY ?e }}")
    for p in Prop_o:
        prop = p.split('#')[1] if '#' in p else p.split('/')[-1]
        parts.append(f"OPTIONAL {{ ?e <{p}> ?o_{prop} .")
        parts.append(f"{{ SELECT ?e (COUNT(?o_{prop}) AS ?{prop}Count) WHERE {{ ?e <{p}> ?o_{prop} }} GROUP BY ?e }} }}")
    
    props_filter = ", ".join(f"<{p}>" for p in Prop_m + Prop_o)
    parts.append(f"MINUS {{ ?e ?prop ?o . FILTER (?prop NOT IN ({props_filter})) }} \n")
    
    # NodeShapes that target class C
    nodeShapes = []
    queryTargetClass = f"""
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    SELECT ?NS WHERE {{ ?NS sh:targetClass <{C}> }}
    """
    for r in execute_query(queryTargetClass, targetSchema):
        nodeShapes.append(r[0])
    
    for p in Prop_m + Prop_o:
        queryTargetSubjectsOf = f"""
        PREFIX sh: <http://www.w3.org/ns/shacl#>
        SELECT ?NS WHERE {{ ?NS sh:targetSubjectsOf <{p}> }}
        """
        for r in execute_query(queryTargetSubjectsOf, targetSchema):
            nodeShapes.append(r[0])
    
    # Integration of NodeShapes Constraints
    for NS in nodeShapes:
        ns_filter = node_shape_resolution(targetSchema, NS, Prop_m, Prop_o)
        if ns_filter:
            parts.append(f"FILTER ({ns_filter})")
    
    parts.append("}")
    return "\n".join(parts)


def format_resource(r):
    """
    Format a resource for SPARQL queries.
    :param r: The resource to format, can be a BNode or URIRef. 
    """
    if isinstance(r,BNode):
        return r.n3()
    elif isinstance(r,URIRef):
        return f'<{str(r)}>'
    else :
        return f'<{str(r)}>'
    
def execute_query(query, targetSchema):
    """
    Execute a SPARQL Query
    :param query: The SPARQL query string to execute.
    :param targetSchema: The RDF graph to query.
    """
    return list(targetSchema.query(query))

def basic_constraint_resolution(p, propsh, k, Prop_m, Prop_o):
    """
    Resolution of a basic constraint on property p from (propsh, k) constraint
    :param p: The property to resolve.
    :param propsh: The constraint property
    :param k: The value of propsh constraint.
    """
    propsh = str(propsh)
    shortprop = p.split('#')[1] if '#' in p else p.split('/')[-1]
    resolution = ""
    
    if propsh == "http://www.w3.org/ns/shacl#class":
        resolution = f"EXISTS {{ ?o_{shortprop} rdf:type <{k}> }}"
    elif propsh == "http://www.w3.org/ns/shacl#datatype":
        resolution = f"datatype(?o_{shortprop}) = <{k}>"
    elif propsh == "http://www.w3.org/ns/shacl#nodeKind":
        node_kind_mapping = {
            "http://www.w3.org/ns/shacl#BlankNode": f"isBlankNode(?o_{shortprop})",
            "http://www.w3.org/ns/shacl#IRI": f"isIRI(?o_{shortprop})",
            "http://www.w3.org/ns/shacl#Literal": f"isLiteral(?o_{shortprop})",
            "http://www.w3.org/ns/shacl#BlankNodeOrIRI": f"(isBlankNode(?o_{shortprop}) || isIRI(?o_{shortprop}))",
            "http://www.w3.org/ns/shacl#BlankNodeOrLiteral": f"(isBlankNode(?o_{shortprop}) || isLiteral(?o_{shortprop}))",
            "http://www.w3.org/ns/shacl#IRIOrLiteral": f"(isLiteral(?o_{shortprop}) || isIRI(?o_{shortprop}))"
        }
        resolution = node_kind_mapping.get(k, "")
    elif propsh in [
        "http://www.w3.org/ns/shacl#minCount",
        "http://www.w3.org/ns/shacl#maxCount",
        "http://www.w3.org/ns/shacl#minInclusive",
        "http://www.w3.org/ns/shacl#minExclusive",
        "http://www.w3.org/ns/shacl#maxInclusive",
        "http://www.w3.org/ns/shacl#maxExclusive",
        "http://www.w3.org/ns/shacl#minLength",
        "http://www.w3.org/ns/shacl#maxLength"
    ]:
        numeric_mapping = {
            "http://www.w3.org/ns/shacl#minCount": ">",
            "http://www.w3.org/ns/shacl#maxCount": "<",
            "http://www.w3.org/ns/shacl#minInclusive": ">=",
            "http://www.w3.org/ns/shacl#minExclusive": ">",
            "http://www.w3.org/ns/shacl#maxInclusive": "<=",
            "http://www.w3.org/ns/shacl#maxExclusive": "<",
            "http://www.w3.org/ns/shacl#minLength": f">= STRLEN(str(?o_{shortprop}))",
            "http://www.w3.org/ns/shacl#maxLength": f"<= STRLEN(str(?o_{shortprop}))"
        }
        resolution = f"?o_{shortprop} {numeric_mapping[propsh]} {k}"
    elif propsh == "http://www.w3.org/ns/shacl#pattern":
        resolution = f'regex(?o_{shortprop}, "{k}")'
    elif propsh in ["http://www.w3.org/ns/shacl#languageIn", "http://www.w3.org/ns/shacl#uniqueLang"]:
        resolution = f'lang(?o_{shortprop}) IN ("{k}")'
    elif propsh in ["http://www.w3.org/ns/shacl#hasValue", "http://www.w3.org/ns/shacl#in"]:
        resolution = f'?o_{shortprop} IN ("{k}")'
    elif propsh in [
        "http://www.w3.org/ns/shacl#lessThan",
        "http://www.w3.org/ns/shacl#lessThanOrEquals",
        "http://www.w3.org/ns/shacl#equals",
        "http://www.w3.org/ns/shacl#disjoint"
    ] and '#' in k:
        comparison_mapping = {
            "http://www.w3.org/ns/shacl#lessThan": "<",
            "http://www.w3.org/ns/shacl#lessThanOrEquals": "<=",
            "http://www.w3.org/ns/shacl#equals": "=",
            "http://www.w3.org/ns/shacl#disjoint": "!="
        }
        comparison_prop = k.split('#')[1]
        resolution = f"?o_{shortprop} {comparison_mapping[propsh]} ?o_{comparison_prop}"
    
    if p in Prop_o:
        resolution = f"!bound(?o_{shortprop}) || {resolution}"
    return resolution


def main():
    parser = argparse.ArgumentParser(description="Mon script avec paramètres")
    parser.add_argument("--input", type=str, required=True, help="book, movie, person, product, tvseries,one_simple, one_complex, three_simple, three_complex, runningExample")
    
    args = parser.parse_args()

    targetSchema = Graph()
    if args.input not in ["book", "movie", "person", "product", "tvseries", "runningExample", "one_simple", "one_complex", "three_simple", "three_complex"]:
        print("This configuration is not none. Please enter a valid configuration.")
        return
    elif args.input == "book":
        pathShapes = "/Sources/book_shape.ttl"
        C1 = "http://schema.org/Book"
        Prop_m1 = ["http://schema.org/identifier", "http://schema.org/name", "http://schema.org/bookEdition", "http://schema.org/isbn",
                    "http://schema.org/numberOfPages", "http://schema.org/author", "http://schema.org/dateCreated", "http://schema.org/datePublished",
                    "http://schema.org/genre", "http://schema.org/award", "http://schema.org/inLanguage"]
        Prop_o1 = []
        C2 = "http://schema.org/Person"
        Prop_m2 = ["http://schema.org/givenName", "http://schema.org/bithDate", "http://schema.org/gender",  "http://schema.org/email",
                    "http://schema.org/telephone"]
        Prop_o2 = [ "http://schema.org/deathDate"]

        targetSchema.parse(pathShapes, format="ttl")
        # Skolemise le graphe pour remplacer les blank nodes par des IRIs stables.
        targetSchema = targetSchema.skolemize()

        extraction_query1 = generate_extraction_query(targetSchema, C1, Prop_m1, Prop_o1)
        extraction_query2 = generate_extraction_query(targetSchema, C2, Prop_m2, Prop_o2)

        print("Query Generatd for target class Book: \n" + str(extraction_query1) + "\n\n")
        print("Query Generatd for target class Person: \n" + str(extraction_query2) + "\n\n")


    elif args.input == "movie":
        pathShapes = "/Sources/movie_shape.ttl"
        C1 = "http://schema.org/Movie"
        Prop_m1 = ["http://schema.org/director", "http://schema.org/award", "http://schema.org/name", "http://schema.org/dateCreated",
                "http://schema.org/datePublished","http://schema.org/genre","http://schema.org/inLanguage"]
        Prop_o1 = []
        C2 = "http://schema.org/Person"
        Prop_m2 = ["http://schema.org/givenName", "http://schema.org/gender",  "http://schema.org/email",
                "http://schema.org/telephone"]
        Prop_o2 = []

        targetSchema.parse(pathShapes, format="ttl")
        # Skolemise le graphe pour remplacer les blank nodes par des IRIs stables.
        targetSchema = targetSchema.skolemize()
        extraction_query1 = generate_extraction_query(targetSchema, C1, Prop_m1, Prop_o1)
        extraction_query2 = generate_extraction_query(targetSchema, C2, Prop_m2, Prop_o2)

        print("Query Generatd for target class Movie: \n" + str(extraction_query1) + "\n\n")
        print("Query Generatd for target class Person: \n" + str(extraction_query2) + "\n\n")

    elif args.input == "person":
        pathShapes = "/Sources/person_shape.ttl"
        C1 = "http://schema.org/Address"
        Prop_m1 = ["http://schema.org/streetAddress", "http://schema.org/postalCode"]
        Prop_o1 = []
        C2 = "http://schema.org/Person"
        Prop_m2 = ["http://schema.org/givenName", "http://schema.org/name","http://schema.org/familyName", "http://schema.org/bithDate",
                "http://schema.org/gender",  "http://schema.org/email", "http://schema.org/jobTitle", "http://schema.org/address",
                "http://schema.org/telephone"]
        Prop_o2 = [ "http://schema.org/deathDate"]

        targetSchema.parse(pathShapes, format="ttl")
        # Skolemise le graphe pour remplacer les blank nodes par des IRIs stables.
        targetSchema = targetSchema.skolemize()

        extraction_query1 = generate_extraction_query(targetSchema, C1, Prop_m1, Prop_o1)
        extraction_query2 = generate_extraction_query(targetSchema, C2, Prop_m2, Prop_o2)

        print("Query Generatd for target class Address: \n" + str(extraction_query1) + "\n\n")
        print("Query Generatd for target class Person: \n" + str(extraction_query2) + "\n\n")


    elif args.input == "product":
        pathShapes = "/Sources/example_product_shape.ttl"
        C1 = "http://example.com/ns#Product"
        Prop_m1 = ["http://example.com/ns#identifier", "http://example.com/ns#name", "http://example.com/ns#dateOrProduction","http://example.com/ns#dateOfExpiration"]
        Prop_o1 = []

        targetSchema.parse(pathShapes, format="ttl")
        # Skolemise le graphe pour remplacer les blank nodes par des IRIs stables.
        targetSchema = targetSchema.skolemize()

        extraction_query1 = generate_extraction_query(targetSchema, C1, Prop_m1, Prop_o1)
        print("Query Generatd for target class Product: \n" + str(extraction_query1) + "\n\n")

    elif args.input == "tvseries":
        pathShapes = "/Sources/tv_series_shape.ttl"
        C1 = "http://schema.org/TVSeries"
        Prop_m1 = ["http://schema.org/director", "http://schema.org/actor", "http://schema.org/season","http://schema.org/numberOfEpisodes",
                "http://schema.org/numberOfSeasons","http://schema.org/startDate", "http://schema.org/endDate", "http://schema.org/datePublished", 
                "http://schema.org/genre", "http://schema.org/titleEIDR","http://schema.org/name"]
        Prop_o1 = []
        C2 = "http://schema.org/Person"
        Prop_m2 = ["http://schema.org/givenName", "http://schema.org/familyName","http://schema.org/gender",  
                    "http://schema.org/email", "http://schema.org/telephone"]
        Prop_o2 = []

        C3 = "http://schema.org/Person"
        Prop_m3 = ["http://schema.org/gender","http://schema.org/name"]
        Prop_o3 = []
        
        targetSchema.parse(pathShapes, format="ttl")
        # Skolemise le graphe pour remplacer les blank nodes par des IRIs stables.
        targetSchema = targetSchema.skolemize()

        extraction_query1 = generate_extraction_query(targetSchema, C1, Prop_m1, Prop_o1)
        extraction_query2 = generate_extraction_query(targetSchema, C2, Prop_m2, Prop_o2)   
        extraction_query3 = generate_extraction_query(targetSchema, C3, Prop_m3, Prop_o3)

        print("Query Generatd for target class TVSeries: \n" + str(extraction_query1) + "\n\n")
        print("Query Generatd for target class Person: \n" + str(extraction_query2) + "\n\n")
        print("Query Generatd for target class Person: \n" + str(extraction_query3) + "\n\n")

    elif args.input == "runningExample":
        pathShapes = "/Sources/runningExample.ttl"
        C1 = "http://example.com/ns#Journal"
        Prop_m1 = ["http://example.com/ns#journalName", "http://example.com/ns#issn"]
        Prop_o1 = []
        C2 = "http://example.com/ns#Author"
        Prop_m2 = ["http://example.com/ns#fullName", "http://example.com/ns#affiliation"]
        Prop_o2 = ["http://example.com/ns#ex:orcid", "http://example.com/ns#notes"]
        C3 = "http://example.com/ns#Conference"
        Prop_m3 = ["http://example.com/ns#confName", "http://example.com/ns#location","http://example.com/ns#date"]
        Prop_o3 = []
        C4 = "http://example.com/ns#Article"
        Prop_m4 = ["http://example.com/ns#title", "http://example.com/ns#date", "http://example.com/ns#publishedIn", "http://example.com/ns#presentedAt", "http://example.com/ns#hasAuthor"]
        Prop_o4 = ["http://example.com/ns#abstract", "http://example.com/ns#keyword"]

        targetSchema.parse(pathShapes, format="ttl")
        # Skolemise le graphe pour remplacer les blank nodes par des IRIs stables.
        targetSchema = targetSchema.skolemize()
        extraction_query1 = generate_extraction_query(targetSchema, C1, Prop_m1, Prop_o1)
        extraction_query2 = generate_extraction_query(targetSchema, C2, Prop_m2, Prop_o2)
        extraction_query3 = generate_extraction_query(targetSchema, C3, Prop_m3, Prop_o3)
        extraction_query4 = generate_extraction_query(targetSchema, C4, Prop_m4, Prop_o4)

        print("Query Generatd for target class Journal: \n" + str(extraction_query1) + "\n\n")
        print("Query Generatd for target class Author: \n" + str(extraction_query2) + "\n\n")
        print("Query Generatd for target class Conference: \n" + str(extraction_query3) + "\n\n")
        print("Query Generatd for target class Article: \n" + str(extraction_query4) + "\n\n")

    elif args.input == "one_simple":
        pathShapes = "/Sources/shape-single-simple.ttl"
        C = "http://example.com/ns#ExampleClass"
        Prop_m = ["http://example.com/ns#randomProperty"]
        Prop_o = []

        targetSchema.parse(pathShapes, format="ttl")
        # Skolemise le graphe pour remplacer les blank nodes par des IRIs stables.
        targetSchema = targetSchema.skolemize()
        extraction_query = generate_extraction_query(targetSchema, C, Prop_m, Prop_o)
        print("Query Generatd for target class ExampleClass: \n" + str(extraction_query) + "\n\n")
    
    elif args.input == "one_complex":
        pathShapes = "/Sources/shape-single-complex.ttl"
        C = "http://example.com/ns#ExampleClass"
        Prop_m = ["http://example.com/ns#randomProperty", "http://example.com/ns#anotherRandomProperty", "http://example.com/ns#date1", "http://example.com/ns#date2"]
        Prop_o = []

        targetSchema.parse(pathShapes, format="ttl")
        # Skolemise le graphe pour remplacer les blank nodes par des IRIs stables.
        targetSchema = targetSchema.skolemize()
        extraction_query = generate_extraction_query(targetSchema, C, Prop_m, Prop_o)
        print("Query Generatd for target class ExampleClass: \n" + str(extraction_query) + "\n\n")
    
    elif args.input == "three_simple":
        pathShapes = "/Sources/shape-three-simple.ttl"
        C1 = "http://example.com/ns#ExampleClass"
        Prop_m1 = ["http://example.com/ns#randomProperty", "http://example.com/ns#firstConnectingProperty", "http://example.com/ns#secondConnectionProperty"]
        Prop_o1 = []
        C2 = "http://example.com/ns#Address"
        Prop_m2 = ["http://example.com/ns#addressValue"]
        Prop_o2 = []
        C3 = "http://example.com/ns#Phone"
        Prop_m3 = ["http://example.com/ns#phoneValue"]
        Prop_o3= []

        targetSchema.parse(pathShapes, format="ttl")
        # Skolemise le graphe pour remplacer les blank nodes par des IRIs stables.
        targetSchema = targetSchema.skolemize()
        extraction_query1 = generate_extraction_query(targetSchema, C1, Prop_m1, Prop_o1)
        extraction_query2 = generate_extraction_query(targetSchema, C2, Prop_m2, Prop_o2)
        extraction_query3 = generate_extraction_query(targetSchema, C3, Prop_m3, Prop_o3)
        print("Query Generatd for target class ExampleClass: \n" + str(extraction_query1) + "\n\n")
        print("Query Generatd for target class Address: \n" + str(extraction_query2) + "\n\n")
        print("Query Generatd for target class Phone: \n" + str(extraction_query3) + "\n\n")

    elif args.input == "three_complex":
        pathShapes = "/Sources/shape-three-complex.ttl"
        C1 = "http://example.com/ns#ExampleClass"
        Prop_m1 = ["http://example.com/ns#randomProperty","http://example.com/ns#anotherRandomProperty", "http://example.com/ns#firstConnectingProperty", "http://example.com/ns#secondConnectionProperty"]
        Prop_o1 = []
        C2 = "http://example.com/ns#Address"
        Prop_m2 = ["http://example.com/ns#addressValue"]
        Prop_o2 = []
        C3 = "http://example.com/ns#Date"
        Prop_m3 = ["http://example.com/ns#date1","http://example.com/ns#date2" ]
        Prop_o3= []

        targetSchema.parse(pathShapes, format="ttl")
        # Skolemise le graphe pour remplacer les blank nodes par des IRIs stables.
        targetSchema = targetSchema.skolemize()

        extraction_query1 = generate_extraction_query(targetSchema, C1, Prop_m1, Prop_o1)
        extraction_query2 = generate_extraction_query(targetSchema, C2, Prop_m2, Prop_o2)
        extraction_query3 = generate_extraction_query(targetSchema, C3, Prop_m3, Prop_o3)

        print("Query Generatd for target class ExampleClass: \n" + str(extraction_query1) + "\n\n")
        print("Query Generatd for target class Address: \n" + str(extraction_query2) + "\n\n")
        print("Query Generatd for target class Date: \n" + str(extraction_query3) + "\n\n")
    


if __name__ == '__main__':
    main()

