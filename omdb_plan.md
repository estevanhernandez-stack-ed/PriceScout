Usage
Send all data requests to:

http://www.omdbapi.com/?apikey=[yourkey]&

Poster API requests:

http://img.omdbapi.com/?apikey=[yourkey]&
Parameters
By ID or Title
Parameter	Required	Valid Options	Default Value	Description
i	Optional*		<empty>	A valid IMDb ID (e.g. tt1285016)
t	Optional*		<empty>	Movie title to search for.
type	No	movie, series, episode	<empty>	Type of result to return.
y	No		<empty>	Year of release.
plot	No	short, full	short	Return short or full plot.
r	No	json, xml	json	The data type to return.
callback	No		<empty>	JSONP callback name.
v	No		1	API version (reserved for future use).
*Please note while both "i" and "t" are optional at least one argument is required.
By Search
Parameter	Required	Valid options	Default Value	Description
s	Yes		<empty>	Movie title to search for.
type	No	movie, series, episode	<empty>	Type of result to return.
y	No		<empty>	Year of release.
r	No	json, xml	json	The data type to return.
page New!	No	1-100	1	Page number to return.
callback	No		<empty>	JSONP callback name.
v	No		1	API version (reserved for future use).
Examples
By Title
Title: 
    Year: 
    Plot: 
Short
    Response: 
JSON
    Search Reset
By ID
ID: 
IMDb ID
    Plot: 
Short
    Response: 
JSON
    Search Reset