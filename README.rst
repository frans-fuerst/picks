Picks - View, pick and tag pictures
===================================

Despite there are lot's and lot's of file viewers out there none of them
satisfied a couple of requirements which are important for me:

- support for 'interesting file separation' (by **copying/linking a file**
  to a special folder while viewing)
- **file tagging** without a proprietary database (best would be tagging in the
  filename because this is intuitive and platform/tool independent)
- sexy **slide show** mode (e.g. with Ken Burns effect (pan/zoom))
- support at least for **Linux**

This is why `picks` (play on the words *picture* and *pick*) emerged. Among
the features already mentioned the project goals are:

- easy **deployment/usage** on at least Linux/MacOS/Windows
- **easy interaction** without the need to use a mouse
- support for reading from attached **smart phones** (MTP support)
- tools for deciding whether to **keep or delete** a file (focus peaking, etc.)


Installation / Usage
--------------------

Recommended way to install picks is via **pip**::

    pip3 install picks


Partly available
----------------

* Single picture mode
    - [x] auto rotate
    - [x] center image
    - [x] keep aspect ratio
    - [ ] anti aliasing
    - [ ] color correction

* Command line args
    - [x] read path on command line

* Sort file list
    - [x] alphabetically

* Full keyboard use
    - [x] Navigate on Page UP/DOWN, Arrow Up/Down/Left/Right/Space/Back
    - [ ] F3/E: Start editor
    - [ ] F5: Slideshow
    - [x] F7: copy
    - [x] F11: toggle fullscreen
    - [x] DEL: delete (move)
    - [ ] F8: link
    - [ ] F9: move
    - [x] T: Start tag editing

* File naming/modify tags stored in filename
    - [x] read and write back a filename with date on CLI
    - [ ] add a tag to a file via UI
    - [ ] remove a tag to a file via UI
    - [ ] modify tags on CLI

* Search
    - [x] among file name

* Nice look
    - [x] dark theme style
    - [ ] icon

* Performance
    - [x] cache viewed files
    - [x] pre cache next file
    - [ ] use different exif library (mind Windows!)

* Persistence
    - [x] store known tags
    - [ ] store current filename (across sessions and list updates)


Not yet implemented
-------------------

* show EXIF information

 * deployment
    - [ ] provide PIP package

* Open from mobile (MTP)

* Usability
    - [ ] inotify folder and update list
    - [ ] show decent popup info on actions

* Read and apply GPS data from GPX tracks

* Gallery mode

* Slideshow mode
    [ ] Ken burns effect

* Open with..

* show movies

* directory navigation

* merge selection viewer

* Zoom
    - [ ] toggle zoom

* Compare pictures
    - [ ] in zoom mode
    - [ ] with focus peaking

* research: open directory dialog

* more sophisticated resizing:
    http://stackoverflow.com/questions/21041941
