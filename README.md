Open MVIS Pages
==============
*Open MVIS* is open-sourced lib for multi-visual-inertial sensor calibration.  
See http://jemdoc.jaboc.net/ for more information and the detailed usage of jemdoc.
We use *jemdoc+MathJax*  with the MathJax support to jemdoc and generate html pages.

How to use generate Open MVIS pages
-------------------------

* Generate the `YOUR_JEMDOC_SCRIPT.jemdoc` following [jemdoc user guide](http://jemdoc.jaboc.net/using.html).

* Generate the `YOUR_JEMDOC_SCRIPT.html` using the configuration `mysite.conf` and put the html file in `Path_folder` with command: 

```
jemdoc -c mysite.conf -o Path_folder YOUR_JEMDOC_SCRIPT.jemdoc
```

* Check the resulting website by opening any HTML files generated by the above command inside a web browser.

Example 
-------------------------

Generate the `index.html` for the Open MVIS project: 
```
cd openmvis 
../jemdoc -c openmvis.conf -o ../docs/ index.jemdoc
```

where 
* `openmvis.conf` is the configuration
* `../docs/` is the path folder
* `index.jemdoc` is the project jemdoc script
	

For Website statistics
```
<script type="text/javascript" id="clustrmaps" src="//clustrmaps.com/map_v2.js?d=7ujQYgpPqBco-N6Vt17BSUFoYlG4wDdbC7HP7Rq3_40&cl=ffffff&w=a"></script>
```



