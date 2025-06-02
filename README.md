# Controlled RDF Data Extraction Under SHACL Constraints

We address the problem of populating a schema from RDF datasets by automatically generating a set of extraction queries. We consider that the data required for a given application is described by a set of target classes, each one associated with a set of SHACL shapes expressing constraints over these classes and their properties. We present a query generation approach that provides a set of SPARQL queries to populate each target class. Our approach ensures that each extracted instance is valid with respect to the SHACL shapes defined on the considered classes. To this end, we define specific filters for each type of constraint, and we propose a recursive algorithm that inserts filters into the queries, ensuring that the logical compositions of constraints defined in SHACL are correctly expressed in the conditions of the queries. We provide some experimental evaluations to highlight the performance of our approach.

## Usage 
To execute the code, you can use the following command: python ControlledRDFDataExtractionUnderSHACLConstraints/main.py --input runningExample
With this execution, you will get query generated for each target class of the example.

You can switch use case by replacing runningExample in the command by one of the following:
- book
- movie
- person
- product
- tvseries
- one_simple
- one_complex
- three_simple
- three_complex

## Sources
The input SHACL shapes are available in repository Sources. Each file correspond to the shapes used in the different use cases. Target classes, with their associated mandatory and optional properties have directly been added to the code. 
