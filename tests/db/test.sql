-- 2 rooms (room1 and room2) where room2 is a public room with "topic here" as the topic
-- room 1 just has s@syn.org in it with a single message "hello world" which is self-delivered for feedback
-- room 2 started with x@syn.org who invited y and z, who eventually join. z then leaves.
-- room 2 has messages from x,y,z,x in that order, with various degrees of feedback.

insert into rooms values (0,"room1",0,NULL);
insert into rooms values (1,"room2",0,NULL);
insert into rooms values (2,"room2",0,"topic here");
insert into rooms values (3,"room2",1,NULL);

insert into messages(id, sender_synid, room_id, msg_id, type, body) values (1,"s@syn.org","room1","msgid1","text","hello world");
insert into messages(id, sender_synid, room_id, msg_id, type, body) values (2,"x@syn.org","room2","msgid1","text","hey guyz");
insert into messages(id, sender_synid, room_id, msg_id, type, body) values (3,"y@syn.org","room2","msgid1","text","yo");
insert into messages(id, sender_synid, room_id, msg_id, type, body) values (4,"z@syn.org","room2","msgid1","text","sup");
insert into messages(id, sender_synid, room_id, msg_id, type, body) values (5,"x@syn.org","room2","msgid1","text","waz goin on");

insert into room_memberships(id, synid, room_id, state) values (1,"x@syn.org","room2","join");
insert into room_memberships(id, synid, room_id, state) values (2,"y@syn.org","room2","invite");
insert into room_memberships(id, synid, room_id, state) values (3,"y@syn.org","room2","join");
insert into room_memberships(id, synid, room_id, state) values (4,"z@syn.org","room2","invite");
insert into room_memberships(id, synid, room_id, state) values (5,"z@syn.org","room2","join");
insert into room_memberships(id, synid, room_id, state) values (6,"z@syn.org","room2","left");
insert into room_memberships(id, synid, room_id, state) values (7,"s@syn.org","room1","join");

insert into feedback values (1,"d","s@syn.org",1);
insert into feedback values (2,"d","y@syn.org",3);
insert into feedback values (3,"r","y@syn.org",3);
insert into feedback values (4,"r","y@syn.org",2);
insert into feedback values (5,"d","y@syn.org",2);
insert into feedback values (6,"d","x@syn.org",3);
insert into feedback values (7,"r","x@syn.org",3);
insert into feedback values (8,"d","x@syn.org",4);
insert into feedback values (9,"r","x@syn.org",4);


-- VERSIONS marked in order:
-- { rooms, messages, room_members, feedback }
-- QUERY: { 2,2,2,2 }
-- SELECT * FROM rooms WHERE id > 2; etc...

-- Getting latest room membership state (e.g. for z@syn.org)
-- SELECT * FROM room_members WHERE synid = "z@syn.org" ORDER BY id DESC LIMIT 1;

-- Getting from= to= versions
-- E.g. getting the last 2 msgs in room2 from ver=5 to ver=2
-- SELECT * FROM messages where id < 5 AND id > 2 ORDER BY id DESC LIMIT 2;
-- NB: The "ORDER BY id DESC" will depend on the direction of the pagination

-- Getting previous 2 msgs from room2 from ver=5
-- SELECT * FROM messages where id < 5 AND room_id="room2" ORDER BY id DESC LIMIT 2;
-- with feedback:
SELECT messages.id, messages.body, temp.json FROM messages LEFT JOIN (select feedback.msg_id, "["||group_concat('{"'||feedback.sender_synid||'":"'||feedback.type,'"},')||'"}]' as json from feedback GROUP BY feedback.msg_id) AS temp ON messages.id = temp.msg_id WHERE messages.id < 5 AND room_id="room2" ORDER BY id DESC LIMIT 2;

-- The statement:
-- select feedback.msg_id, "["||group_concat('{"'||feedback.sender_synid||'":"'||feedback.type,'"},')||'"}]' as json from feedback GROUP BY feedback.msg_id
-- consolidates all feedback for each message and blobs it into a JSON object
