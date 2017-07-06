/* Create a table for representing frame objects. Each frame
   includes an ASCII UUID consisting of the characters
   [0-9a-f\-], an ASCII hexidecimal IPv6 addresses limited
   to 45 characters, and a 23 character date represented with
   a subset of ISO8601.
*/
create table frames(file_name varchar(36), origin_machine varchar(45), time varchar(23));

