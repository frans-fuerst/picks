
Features: Partly available
--------------------------

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
    - [x] add date on CLI
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
    - [x] provide PIP package
    - [ ] make ``pick`` command available via Gnome shell
    - [ ] install PyQt5
    - [ ] work on Windows
    - [ ] work on MacOS

* Open from mobile (MTP)

* Usability
    - [x] show decent popup info on actions
    - [ ] inotify folder and update file list automatically

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
