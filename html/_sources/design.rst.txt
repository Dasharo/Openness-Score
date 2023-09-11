Dasharo Openness Score design
=============================

Dasharo Openness Score is designed following a few patterns and design rules.


Dasharo Openness Score general rules
------------------------------------

1. The utility should not leave any intermediate files during the firmware
   image processing.
2. The utility should produce a markdown report and two pie charts:

   * First pie chart should incudle the overall share percentage of all 4
     groups: closed-source, open-source, empty and data
   * Second pie chart should incudle the overall share percentage of total
     closed-source and open-source code only
   * Markdown report should print general image statistics and any additional
     statistic per region or firmware integral part (firmware image type
     dependent) includign the category the component has been classified
   * General image statistic at minimum are: image size, open-source size,
     closed-source size, data size and empty size

3. The utility must be sa precise as possible to avoid falsified results.

Dasharo Openness Score module design rules
------------------------------------------

Each class representing a firmware image (or its integral part):

1. Must calculate the 4 basic metrics (empty, data, closed-source and
   open-source) on the class instance creation.
2. Should have a string method ``__str__`` which returns a set of 4 basic
   metrics and general attributes of the entity
3. Should have a length method ``__len__`` which returns the size of the
   firmware image (or its integral part)
4. Must contain attributes for the basic metrics using the following names:
   ``self.open_code_size``, ``self.closed_code_size``, ``self.data_size`` and
   ``self.empty_size``
5. Must implement ``export_markdown`` method that will produce a markdown
   report of the firmware image (or its integral part) statistics
6. Must implement ``_calculate_metrics`` method which will perform the image
   component classification and do the calculations
7. Should implement a parse method which will perform the extraction of the
   image components and its attributes
8. Must call the parse method and ``_calculate_metrics`` inside the class'
  ``__init__`` method
9. Must implement ``export_charts`` method to generate pie charts (only for
   classes representing the whole firmware image)
10. Must assume a component as closed-source if unable to classify to any
    category.
