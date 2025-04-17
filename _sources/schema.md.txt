The required dropbox format is a *.eln format which is basically a zipped RO-Crate with a .eln file extension.
For the ro-crate-metadata.json file, follows the RO-Crate 1.1+ Specification, the following structure is expected:

## Properties

- [`Dataset`](https://schema.org/dataset)
  - [`identifier`](https://schema.org/identifier): [`Text`](https://schema.org/Text) or [`URL`](https://schema.org/URL) (required) *on the root element level the PERMID of the object in openBIS, which is linked to the OMERO data*
  - [`additionalType`](https://schema.org/additionalType): [`Text`](https://schema.org/Text) (required) *openBIS object type*
  - [`description`](https://schema.org/description): [`Text`](https://schema.org/Text) (optional)
  - [`author`](https://schema.org/author): [`Person`](https://schema.org/Text) (optional)
  - [`creator`](https://schema.org/creator): [`Person`](https://schema.org/Person) (required) *user in OMERO and openBIS that links the sources together*
  - [`dateCreated`](https://schema.org/dateCreated): [`Date`](https://schema.org/Date) or [`DateTime`](https://schema.org/DateTime) (required) *creation data of the linkage*
  - [`dateModified`](https://schema.org/dateModified): [`Date`](https://schema.org/Date) or [`DateTime`](https://schema.org/DateTime) (required)
  - [`name`](https://schema.org/name): [`Text`](https://schema.org/Text) (required) *on the linked dataset level the name for the ENTRY object in openBIS that will be created*
  - [`text`](https://schema.org/text): [`Text`](https://schema.org/Text) (optional) 
  - [`hasPart`](https://schema.org/hasPart): [`Dataset`](https://schema.org/dataset) (optional) *data from OMERO*
  

- [`Person`](http://schema.org/Person) 
  - [`givenName`](https://schema.org/givenName): [`Text`](https://schema.org/Text) (required)
  - [`familyName`](http://schema.org/familyName): [`Text`](https://schema.org/Text) (required)  
  - [`alternateName`](https://schema.org/alternateName): [`Text`](https://schema.org/Text) (required)  *userID in openBIS*
 
  
- [`SoftwareApplication`](https://schema.org/ScholarlyArticle)
  - [`installUrl`](https://schema.org/installUrl): [`URL`](https://schema.org/URL) (optional)  
  - [`name`](https://schema.org/name): [`Text`](https://schema.org/Text) (required)
  - [`softwareVersion`](https://schema.org/softwareVersion): [`Text`](https://schema.org/Text) (optional) 
   
- [`CreateAction`](https://schema.org/CreateAction) , see also [Provenance ro-crate](https://www.researchobject.org/ro-crate/specification/1.1/provenance.html)
  - [`object`](https://schema.org/object)(required)
  - [`name`](https://schema.org/name)(optional)
  - [`instrument`](https://schema.org/instrument)(required)
  - [`actionStatus`](https://schema.org/actionStatus)(optional)
  - [`endTime`](https://schema.org/endTime)(optional)
 
**Example:** [ro-crate-metadata.json](ro-crate-metadata_example.json)

