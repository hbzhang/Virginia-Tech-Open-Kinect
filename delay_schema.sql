/* 
   Create a table for representing delay objects. ASCII hexidecimal
   IPv6 addresses limited to 45 characters, and a 23 character date
   represented with a subset of ISO8601.
*/
create table delay(origin_machine varchar(45), time_elapsed varchar(23));
