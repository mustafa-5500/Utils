
**Date:** 2026-08-19
Previous Entry: Initial Log

**Developer:**
    - Mustafa

**Comments:**
This is the first log since we created the Utils repository. We successfully split the repository out from the Building-Lore Linking plugin repository.

Furthermore, we create a dev-log script to help make logging easier for the developer while maintaing good practices such as listing goals and actions. The command is `./gradlew devlog` which creates the current dates developer log if it does not exist, and opens the dev log. As well as recording the developer name from the git config information, so we can track who worked when to help collaboration.

Things we want to make in the future is improving on the decomposition generator fucntions, having it include links to the data flow images, and compiling them into SVGs probably by having a portable Plantuml server. Also including the ability to toggle the layers of the data flow, which would probably be switching between SVGs. And having dataflow for each function in function specific locations.


**Goals:**
    - Improve decomposition generator by including links in the plantuml diagram
    - Create a protable Plantuml server to generate the text files into SVGs
    - Encorporate the Plantuml diagrams into the documentation files so that we can see differing levels of data flow as well as function specific data flow.
    - Have higher level system level dataflow diagrams to show how different classes and systems interact.

**Actions:**
    - {add any actions being done}