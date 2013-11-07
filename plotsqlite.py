# -*- coding: utf-8 -*-
"""
/***************************************************************************
Name                 : PlotSQLite
Description          : Plots charts from data stored in a SQLite database
Date                 : 2012-12-03 
Author               : Josef Källgården
email                : groundwatergis@gmail.com 
 ***************************************************************************/
 CHANGELOG:
 v0.2.4 - new build due to a PyInstaller bug (http://www.pyinstaller.org/ticket/783)
 v0.2.3 - added xy scatter plot support, fixed tab order
 v0.2.2 - sorting of filters
 v0.2.1 - encoding cleanupexcluded default splite tables from being listed
 v0.2 - discontinuous plot
 v0.x - early pre-alpha release
 
 
"""
# Import the sys, os, locale and PyQt libraries
import sys, os, locale
from PyQt4 import QtGui, QtCore, uic#, QtSql
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from functools import partial # only to get combobox signals to work

# 
from sqlite3 import dbapi2 as sqlite
import numpy as np
import matplotlib.pyplot as plt   
from matplotlib.dates import datestr2num
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QTAgg as NavigationToolbar
import datetime
import matplotlib.ticker as tick
from PlotSQLite_MainWindow import Ui_MainWindow
from configobj import ConfigObj


class MainWindow(QtGui.QMainWindow, Ui_MainWindow):
    def __init__(self, parent = None):
        #QtGui.QMainWindow.__init__(self, parent)#the line below is for some reason preferred
        super(MainWindow, self).__init__(parent)#for some reason this is supposed to be better than line above
        #QDialog.__init__( self ) #if not working with an application with mainwindow
        #self.iface = iface

        #self=Ui_MainWindow()#new
                
        self.setupUi( self )#due to initialisation of Ui_MainWindow instance
        self.initUI()
        self.maxtstep = 0
        #self.database = ''
        #self.table1 = ''
        #self.database_pyqt4provider = QtSql.QSqlDatabase.addDatabase("QSQLITE","db1")
        
    def initUI(self):
        self.table_ComboBox_1.clear()  
        self.table_ComboBox_2.clear()  
        self.table_ComboBox_3.clear()  
        for i in range (1,3):
            self.clearthings(1)
        self.quit_Qaction.triggered.connect(self.quit_app)
        self.actionAbout.triggered.connect(self.about)          
        self.selectDB_QAction.triggered.connect(self.selectFile)          
        self.selectDB_QPushButton.clicked.connect(self.selectFile)          
        # whenever Time Series Table is changed, the column-combobox must be updated and TableCheck must be performed (function partial due to problems with currentindexChanged and Combobox)
        #self.connect(self.table_ComboBox_1, QtCore.SIGNAL("currentIndexChanged(int)"), partial(self.Table1Changed))#currentIndexChanged caused unnecessary signals when scrolling in combobox
        self.connect(self.table_ComboBox_1, QtCore.SIGNAL("activated(int)"), partial(self.Table1Changed))  
        self.connect(self.Filter1_ComboBox_1, QtCore.SIGNAL("activated(int)"), partial(self.Filter1_1Changed))
        self.connect(self.Filter2_ComboBox_1, QtCore.SIGNAL("activated(int)"), partial(self.Filter2_1Changed)) 
        self.connect(self.table_ComboBox_2, QtCore.SIGNAL("activated(int)"), partial(self.Table2Changed)) 
        self.connect(self.Filter1_ComboBox_2, QtCore.SIGNAL("activated(int)"), partial(self.Filter1_2Changed))
        self.connect(self.Filter2_ComboBox_2, QtCore.SIGNAL("activated(int)"), partial(self.Filter2_2Changed)) 
        self.connect(self.table_ComboBox_3, QtCore.SIGNAL("activated(int)"), partial(self.Table3Changed)) 
        self.connect(self.Filter1_ComboBox_3, QtCore.SIGNAL("activated(int)"), partial(self.Filter1_3Changed))
        self.connect(self.Filter2_ComboBox_3, QtCore.SIGNAL("activated(int)"), partial(self.Filter2_3Changed)) 
        self.PlotChart_QPushButton.clicked.connect(self.drawPlot)
        self.Redraw_pushButton.clicked.connect( self.refreshPlot )
        
        # Create a plot window with one single subplot
        self.figure = plt.figure() 
        self.axes = self.figure.add_subplot( 111 )
        self.canvas = FigureCanvas( self.figure )
        self.mpltoolbar = NavigationToolbar( self.canvas, self.widgetPlot )
        lstActions = self.mpltoolbar.actions()
        self.mpltoolbar.removeAction( lstActions[ 7 ] )
        self.layoutplot.addWidget( self.canvas )
        self.layoutplot.addWidget( self.mpltoolbar )

        # Search for saved settings and load as preset values
        self.settings = QtCore.QSettings('foo','foo')
        self.readsettings()

        self.show()
        
    def quit_app(self):
        self.close()
        #QtSql.QSqlDatabase.removeDatabase("db1")
        QtCore.QCoreApplication.instance().quit()

    def drawPlot(self):
        QtGui.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))#show the user this may take a long time...

        self.storesettings()    #db, table, x-col and y-col are saved as default values when user clicks 'plot chart'
        self.axes.clear()
        My_format = [('date_time', datetime.datetime), ('values', float)] #Define (with help from function datetime) a good format for numpy array
        
        conn = sqlite.connect(unicode(self.selected_database_QLineEdit.text()),detect_types=sqlite.PARSE_DECLTYPES|sqlite.PARSE_COLNAMES)#should be cross-platform
        # skapa en cursor
        curs = conn.cursor()

        i = 0
        nop=0# nop=number of plots
        self.p=[]
        self.plabels=[]
        if not (self.table1 == '' or self.table1==' ') and not (self.xcol1== '' or self.xcol1==' ') and not (self.ycol1== '' or self.ycol1==' '): #if anything is to be plotted from tab 1
            self.maxtstep = self.spnmaxtstep.value()   # if user selected a time step bigger than zero than thre may be discontinuous plots
            plottable1='y'
            filter1 = unicode(self.Filter1_ComboBox_1.currentText())
            filter1list = self.Filter1_QListWidget_1.selectedItems()
            filter2 = unicode(self.Filter2_ComboBox_1.currentText())
            filter2list= self.Filter2_QListWidget_1.selectedItems()
            nop += max(len(filter1list),1)*max(len(filter2list),1)
            #self.p= [None]*nop#list for plot objects
            self.p.extend([None]*nop)#list for plot objects
            self.plabels.extend([None]*nop)# List for plot labels
            while i < len(self.p):
                if not (filter1 == '' or filter1==' ') and not (filter2== '' or filter2==' '):
                    for item1 in filter1list:
                        for item2 in filter2list:
                            sql = r""" select """ + unicode(self.xcol_ComboBox_1.currentText()) + """, """ + unicode(self.ycol_ComboBox_1.currentText()) + """ from """ + unicode(self.table_ComboBox_1.currentText()) + """ where """ + filter1 + """='""" + unicode(item1.text())+ """' and """ + filter2 + """='""" + unicode(item2.text())+ """' order by """ + unicode(self.xcol_ComboBox_1.currentText())
                            self.plabels[i] = unicode(item1.text()) + """, """ + unicode(item2.text())
                            self.createsingleplotobject(sql,i,My_format,curs,self.PlotType_comboBox_1.currentText())
                            i += 1
                elif not (filter1 == '' or filter1==' '):
                    for item1 in filter1list:
                        sql = r""" select """ + unicode(self.xcol_ComboBox_1.currentText()) + """, """ + unicode(self.ycol_ComboBox_1.currentText()) + """ from """ + unicode(self.table_ComboBox_1.currentText()) + """ where """ + filter1 + """='""" + unicode(item1.text())+ """' order by """ + unicode(self.xcol_ComboBox_1.currentText())
                        self.plabels[i] = unicode(item1.text()) 
                        self.createsingleplotobject(sql,i,My_format,curs,self.PlotType_comboBox_1.currentText())
                        i += 1
                elif not (filter2 == '' or filter2==' '):
                    for item2 in filter2list:
                        sql = r""" select """ + unicode(self.xcol_ComboBox_1.currentText()) + """, """ + unicode(self.ycol_ComboBox_1.currentText()) + """ from """ + unicode(self.table_ComboBox_1.currentText()) + """ where """ + filter2 + """='""" + unicode(item2.text())+ """' order by """ + unicode(self.xcol_ComboBox_1.currentText())
                        self.plabels[i] = unicode(item2.text())
                        self.createsingleplotobject(sql,i,My_format,curs,self.PlotType_comboBox_1.currentText())
                        i += 1            
                else:
                    sql = r""" select """ + unicode(self.xcol_ComboBox_1.currentText()) + """, """ + unicode(self.ycol_ComboBox_1.currentText()) + """ from """ + unicode(self.table_ComboBox_1.currentText()) + """ order by """ + unicode(self.xcol_ComboBox_1.currentText())
                    self.plabels[i] = unicode(self.ycol_ComboBox_1.currentText())+""", """+unicode(self.table_ComboBox_1.currentText())
                    self.createsingleplotobject(sql,i,My_format,curs,self.PlotType_comboBox_1.currentText())
                    i += 1

        if not (self.table2 == '' or self.table2==' ') and not (self.xcol2== '' or self.xcol2==' ') and not (self.ycol2== '' or self.ycol2==' '):#if anything is to be plotted from tab 2
            self.maxtstep = self.spnmaxtstep.value()   # if user selected a time step bigger than zero than thre may be discontinuous plots
            plottable2='y'
            filter1 = unicode(self.Filter1_ComboBox_2.currentText())
            filter1list = self.Filter1_QListWidget_2.selectedItems()
            filter2 = unicode(self.Filter2_ComboBox_2.currentText())
            filter2list= self.Filter2_QListWidget_2.selectedItems()
            nop =+ max(len(filter1list),1)*max(len(filter2list),1)
            self.p.extend([None]*nop)#list for plot objects
            self.plabels.extend([None]*nop)# List for plot labels
            while i < len(self.p):
                if not (filter1 == '' or filter1==' ') and not (filter2== '' or filter2==' '):
                    for item1 in filter1list:
                        for item2 in filter2list:
                            sql = r""" select """ + unicode(self.xcol2) + """, """ + unicode(self.ycol2) + """ from """ + unicode(self.table2) + """ where """ + filter1 + """='""" + unicode(item1.text())+ """' and """ + filter2 + """='""" + unicode(item2.text())+ """' order by """ + unicode(self.xcol2)
                            self.plabels[i] = unicode(item1.text()) + """, """ + unicode(item2.text())
                            self.createsingleplotobject(sql,i,My_format,curs,self.PlotType_comboBox_2.currentText())
                            i += 1
                elif not (filter1 == '' or filter1==' '):
                    for item1 in filter1list:
                        sql = r""" select """ + unicode(self.xcol2) + """, """ + unicode(self.ycol2) + """ from """ + unicode(self.table2) + """ where """ + filter1 + """='""" + unicode(item1.text())+ """' order by """ + unicode(self.xcol2)
                        self.plabels[i] = unicode(item1.text()) 
                        self.createsingleplotobject(sql,i,My_format,curs,self.PlotType_comboBox_2.currentText())
                        i += 1
                elif not (filter2 == '' or filter2==' '):
                    for item2 in filter2list:
                        sql = r""" select """ + unicode(self.xcol2) + """, """ + unicode(self.ycol2) + """ from """ + unicode(self.table2) + """ where """ + filter2 + """='""" + unicode(item2.text())+ """' order by """ + unicode(self.xcol2)
                        self.plabels[i] = unicode(item2.text())
                        self.createsingleplotobject(sql,i,My_format,curs,self.PlotType_comboBox_2.currentText())
                        i += 1            
                else:
                    sql = r""" select """ + unicode(self.xcol2) + """, """ + unicode(self.ycol2) + """ from """ + unicode(self.table2) + """ order by """ + unicode(self.xcol2)
                    self.plabels[i] = unicode(self.ycol2)+""", """+unicode(self.table2)
                    self.createsingleplotobject(sql,i,My_format,curs,self.PlotType_comboBox_2.currentText())
                    i += 1
            
        if not (self.table3 == '' or self.table3==' ') and not (self.xcol3== '' or self.xcol3==' ') and not (self.ycol3== '' or self.ycol3==' '):#if anything is to be plotted from tab 3
            self.maxtstep = self.spnmaxtstep.value()   # if user selected a time step bigger than zero than thre may be discontinuous plots
            plottable3='y'
            filter1 = unicode(self.Filter1_ComboBox_3.currentText())
            filter1list = self.Filter1_QListWidget_3.selectedItems()
            filter2 = unicode(self.Filter2_ComboBox_3.currentText())
            filter2list= self.Filter2_QListWidget_3.selectedItems()
            nop =+ max(len(filter1list),1)*max(len(filter2list),1)
            self.p.extend([None]*nop)#list for plot objects
            self.plabels.extend([None]*nop)# List for plot labels
            while i < len(self.p):
                if not (filter1 == '' or filter1==' ') and not (filter2== '' or filter2==' '):
                    for item1 in filter1list:
                        for item2 in filter2list:
                            sql = r""" select """ + unicode(self.xcol3) + """, """ + unicode(self.ycol3) + """ from """ + unicode(self.table3) + """ where """ + filter1 + """='""" + unicode(item1.text())+ """' and """ + filter2 + """='""" + unicode(item2.text())+ """' order by """ + unicode(self.xcol3)
                            self.plabels[i] = unicode(item1.text()) + """, """ + unicode(item2.text())
                            self.createsingleplotobject(sql,i,My_format,curs,self.PlotType_comboBox_3.currentText())
                            i += 1
                elif not (filter1 == '' or filter1==' '):
                    for item1 in filter1list:
                        sql = r""" select """ + unicode(self.xcol3) + """, """ + unicode(self.ycol3) + """ from """ + unicode(self.table3) + """ where """ + filter1 + """='""" + unicode(item1.text())+ """' order by """ + unicode(self.xcol3)
                        self.plabels[i] = unicode(item1.text()) 
                        self.createsingleplotobject(sql,i,My_format,curs,self.PlotType_comboBox_3.currentText())
                        i += 1
                elif not (filter2 == '' or filter2==' '):
                    for item2 in filter2list:
                        sql = r""" select """ + unicode(self.xcol3) + """, """ + unicode(self.ycol3) + """ from """ + unicode(self.table3) + """ where """ + filter2 + """='""" + unicode(item2.text())+ """' order by """ + unicode(self.xcol3)
                        self.plabels[i] = unicode(item2.text())
                        self.createsingleplotobject(sql,i,My_format,curs,self.PlotType_comboBox_3.currentText())
                        i += 1            
                else:
                    sql = r""" select """ + unicode(self.xcol3) + """, """ + unicode(self.ycol3) + """ from """ + unicode(self.table3) + """ order by """ + unicode(self.xcol3)
                    self.plabels[i] = unicode(self.ycol3)+""", """+unicode(self.table3)
                    self.createsingleplotobject(sql,i,My_format,curs,self.PlotType_comboBox_3.currentText())
                    i += 1

        #rs.close() # close the cursor
        conn.close()  # close the database
        self.refreshPlot()
        QtGui.QApplication.restoreOverrideCursor()#now this long process is done and the cursor is back as normal

    def createsingleplotobject(self,sql,i,My_format,curs,plottype='line'):
        rs = curs.execute(sql) #Send SQL-syntax to cursor
        recs = rs.fetchall()  # All data are stored in recs
        # late fix for xy-plots
        My_format2 = [('numx', float), ('values', float)]#define a format for xy-plot (to use if not datetime on x-axis)
        #Transform data to a numpy.recarray
        try:
            table = np.array(recs, dtype=My_format)  #NDARRAY
            table2=table.view(np.recarray)   # RECARRAY transform the 2 cols into callable objects
            myTimestring = []  #LIST
            FlagTimeXY = 'time'
            j = 0
            for row in table2: 
                myTimestring.append(table2.date_time[j])
                j = j + 1
            numtime=datestr2num(myTimestring)  #conv list of strings to numpy.ndarray of floats
        except:
            table = np.array(recs, dtype=My_format2)  #NDARRAY
            table2=table.view(np.recarray)   # RECARRAY transform the 2 cols into callable objects
            myXYstring = []  #LIST
            FlagTimeXY = 'XY'
            j = 0
            for row in table2: #
                myXYstring.append(table2.numx[j])
                j = j + 1
            numtime = myXYstring

        # from version 0.2 there is a possibility to make discontinuous plot if timestep bigger than maxtstep
        if self.maxtstep > 0: # if user selected a time step bigger than zero than thre may be discontinuous plots
            pos = np.where(np.abs(np.diff(numtime)) >= self.maxtstep)[0]
            numtime[pos] = np.nan
            table2.values[pos] = np.nan

        if plottype == "marker":
            MarkVar = 'o'  
        elif plottype  == "line":
            MarkVar = '-'  
        elif plottype  == "line and cross":
            MarkVar = '+-'  
        else:
            MarkVar = 'o-'  

        if FlagTimeXY == "time" and plottype == "step-pre":
            self.p[i], = self.axes.plot_date(numtime, table2.values, drawstyle='steps-pre', linestyle='-', marker='None',label=self.plabels[i])# 'steps-pre' best for precipitation and flowmeters, optional types are 'steps', 'steps-mid', 'steps-post'  
        elif FlagTimeXY == "time" and plottype == "step-post":
            self.p[i], = self.axes.plot_date(numtime, table2.values, drawstyle='steps-post', linestyle='-', marker='None',label=self.plabels[i])
        elif FlagTimeXY == "time" and plottype == "line and cross":
            self.p[i], = self.axes.plot_date(numtime, table2.values,  MarkVar,markersize = 6, label=self.plabels[i])
        elif FlagTimeXY == "time":
            self.p[i], = self.axes.plot_date(numtime, table2.values,  MarkVar,label=self.plabels[i])
        elif FlagTimeXY == "XY" and plottype == "step-pre":
            self.p[i], = self.axes.plot(numtime, table2.values, drawstyle='steps-pre', linestyle='-', marker='None',label=self.plabels[i]) 
        elif FlagTimeXY == "XY" and plottype == "step-post":
            self.p[i], = self.axes.plot(numtime, table2.values, drawstyle='steps-post', linestyle='-', marker='None',label=self.plabels[i]) 
        elif FlagTimeXY == "XY" and plottype == "line and cross":
            self.p[i], = self.axes.plot(numtime, table2.values,  MarkVar,markersize = 6, label=self.plabels[i])
        else: 
            self.p[i], = self.axes.plot(numtime, table2.values,  MarkVar,label=self.plabels[i]) 
                
    def refreshPlot( self ):
        self.axes.legend_=None
        #self.axes.clear()
        #self.plabels = ('Rb1103','Rb1104')#debugging
        #print self.plabels #debug
        datemin = self.spnMinX.dateTime().toPyDateTime()
        datemax = self.spnMaxX.dateTime().toPyDateTime()
        if datemin == datemax: #xaxis-limits
            pass
        else:
            self.axes.set_xlim(min(datemin, datemax),max(datemin, datemax))            
        if self.spnMinY.value() == self.spnMaxY.value(): #yaxis-limits
            pass
        else:
            self.axes.set_ylim(min(self.spnMaxY.value(), self.spnMinY.value()),max(self.spnMaxY.value(), self.spnMinY.value()))            
        self.axes.yaxis.set_major_formatter(tick.ScalarFormatter(useOffset=False, useMathText=False))#yaxis-format
        self.figure.autofmt_xdate()#xaxis-format
        self.axes.grid(self.Grid_checkBox.isChecked() )#grid
        if not self.title_QLineEdit.text()=='':#title
            self.axes.set_title(self.title_QLineEdit.text())
        if not self.xtitle_QLineEdit.text()=='':#xaxis label
            self.axes.set_xlabel(self.xtitle_QLineEdit.text())
        if not self.ytitle_QLineEdit.text()=='':#yaxis label
            self.axes.set_ylabel(self.ytitle_QLineEdit.text())
        for label in self.axes.xaxis.get_ticklabels():
            label.set_fontsize(10)
        for label in self.axes.yaxis.get_ticklabels():
            label.set_fontsize(10)
        # finally, the legend
        if self.Legend_checkBox.isChecked():
            if (self.spnLegX.value() ==0 ) and (self.spnLegY.value() ==0):
                leg = self.axes.legend(self.p, self.plabels)
            else:
                leg = self.axes.legend(self.p, self.plabels, bbox_to_anchor=(self.spnLegX.value(),self.spnLegY.value()),loc=10)
            leg.draggable(state=True)
            frame  = leg.get_frame()    # the matplotlib.patches.Rectangle instance surrounding the legend
            frame.set_facecolor('1')    # set the frame face color to white                
            frame.set_fill(False)    # set the frame face color to white                
            for t in leg.get_texts():
                t.set_fontsize(10)    # the legend text fontsize
        else:
            self.axes.legend_=None

        self.figure.autofmt_xdate()
        self.canvas.draw()

    def selectFile(self):   #Open a dialog to locate the sqlite file and some more...
        path = QtGui.QFileDialog.getOpenFileName(None,QtCore.QString.fromLocal8Bit("Select database:"),"*.sqlite")
        if path: 
            self.database = path # To make possible cancel the FileDialog and continue loading a predefined db
        self.openDBFile()

    def openDBFile( self ):    # Open the SpatiaLite file to extract info about tables 
        if os.path.isfile( unicode( self.database ) ):
            self.selected_database_QLineEdit.setText(self.database)
            self.table_ComboBox_1.clear()  
            self.table_ComboBox_2.clear()  
            self.table_ComboBox_3.clear()  
            for i in range (1,3):
                self.clearthings(1)

            conn = sqlite.connect( unicode(self.database) )
            cursor = conn.cursor()
            rs=cursor.execute(r"""SELECT tbl_name FROM sqlite_master WHERE (type='table' or type='view') and not (name in('geom_cols_ref_sys',
                'geometry_columns',
                'geometry_columns_time',
                'spatial_ref_sys',
                'spatialite_history',
                'vector_layers',
                'views_geometry_columns',
                'virts_geometry_columns',
                'geometry_columns_auth',
                'geometry_columns_fields_infos',
                'geometry_columns_statistics',
                'sql_statements_log',
                'layer_statistics',
                'sqlite_sequence',
                'sqlite_stat1' ,
                'views_layer_statistics',
                'virts_layer_statistics',
                'vector_layers_auth',
                'vector_layers_field_infos',
                'vector_layers_statistics',
                'views_geometry_columns_auth',
                'views_geometry_columns_field_infos',
                'views_geometry_columns_statistics',
                'virts_geometry_columns_auth',
                'virts_geometry_columns_field_infos',
                'virts_geometry_columns_statistics' ,
                'geometry_columns',
                'spatialindex',
                'SpatialIndex')) ORDER BY tbl_name"""  )  #SQL statement to get the relevant tables in the spatialite database
            #self.dbTables = {} 
            self.table_ComboBox_1.addItem('')
            self.table_ComboBox_2.addItem('')
            self.table_ComboBox_3.addItem('')
    
            for row in cursor:
                self.table_ComboBox_1.addItem(row[0])
                self.table_ComboBox_2.addItem(row[0])
                self.table_ComboBox_3.addItem(row[0])
            
            rs.close()
            conn.close()        

    def clearthings(self,tabno=1):   #clear xcol,ycol,fukter1,filter2
        xcolcombobox = 'xcol_ComboBox_' + str(tabno)
        ycolcombobox = 'ycol_ComboBox_' + str(tabno)
        filter1combobox = 'Filter1_ComboBox_' + str(tabno)
        filter2combobox = 'Filter2_ComboBox_' + str(tabno)
        filter1qlistwidget = 'Filter1_QListWidget_' + str(tabno)
        filter2qlistwidget = 'Filter2_QListWidget_' + str(tabno)
        getattr(self,xcolcombobox).clear()
        getattr(self,ycolcombobox).clear()
        getattr(self,filter1combobox).clear()
        getattr(self,filter2combobox).clear()
        getattr(self,filter1qlistwidget).clear()
        getattr(self,filter2qlistwidget).clear()

    def Table1Changed(self):     #This method is called whenever table1 is changed
        # First, update combobox with columns
        self.clearthings(1)
        self.table1 = unicode(self.table_ComboBox_1.currentText())
        self.PopulateComboBox('xcol_ComboBox_1', self.table_ComboBox_1.currentText())  # GeneralNote: For some reason it is not possible to send currentText with the SIGNAL-trigger
        self.PopulateComboBox('ycol_ComboBox_1', self.table_ComboBox_1.currentText())  # See GeneralNote
        self.PopulateComboBox('Filter1_ComboBox_1', self.table_ComboBox_1.currentText())  # See GeneralNote
        self.PopulateComboBox('Filter2_ComboBox_1', self.table_ComboBox_1.currentText())  # See GeneralNote

    def Table2Changed(self):     #This method is called whenever table2 is changed
        # First, update combobox with columns
        self.clearthings(2)
        self.table2 = unicode(self.table_ComboBox_2.currentText())
        self.PopulateComboBox('xcol_ComboBox_2', self.table_ComboBox_2.currentText())  # GeneralNote: For some reason it is not possible to send currentText with the SIGNAL-trigger
        self.PopulateComboBox('ycol_ComboBox_2', self.table_ComboBox_2.currentText())  # See GeneralNote
        self.PopulateComboBox('Filter1_ComboBox_2', self.table_ComboBox_2.currentText())  # See GeneralNote
        self.PopulateComboBox('Filter2_ComboBox_2', self.table_ComboBox_2.currentText())  # See GeneralNote

    def Table3Changed(self):     #This method is called whenever table3 is changed
        # First, update combobox with columns
        self.clearthings(3)
        self.table3 = unicode(self.table_ComboBox_3.currentText())
        self.PopulateComboBox('xcol_ComboBox_3', self.table_ComboBox_3.currentText())  # GeneralNote: For some reason it is not possible to send currentText with the SIGNAL-trigger
        self.PopulateComboBox('ycol_ComboBox_3', self.table_ComboBox_3.currentText())  # See GeneralNote
        self.PopulateComboBox('Filter1_ComboBox_3', self.table_ComboBox_3.currentText())  # See GeneralNote
        self.PopulateComboBox('Filter2_ComboBox_3', self.table_ComboBox_3.currentText())  # See GeneralNote

    def PopulateComboBox(self, comboboxname='', table=None):
        """This method fills comboboxes with columns for selected tool and table"""
        columns = self.LoadColumnsFromTable(table)    # Load all columns into a list 'columns'
        if len(columns)>0:    # Transfer information from list 'columns' to the combobox
            getattr(self, comboboxname).addItem('')
            for columnName in columns:
                getattr(self, comboboxname).addItem(columnName)  # getattr is to combine a function and a string to a combined function
        
    def LoadColumnsFromTable(self, table=''):
        """ This method returns a list with all the columns in the table"""
        if len(table)>0 and len(self.database)>0:            # Should not be needed since the function never should be called without existing table...
            conn = sqlite.connect(unicode(self.database))  
            curs = conn.cursor()
            sql = r"""SELECT * FROM '"""
            sql += unicode(table)
            sql += """'"""     
            rs = curs.execute(sql)  #Send the SQL statement to get the columns in the table            
            columns = {} 
            columns = [tuple[0] for tuple in curs.description]
            rs.close()
            conn.close()
        else:
            #QMessageBox.information(None,"info","no table is loaded")    # DEBUGGING
            columns = {}
        return columns        # This method returns a list with all the columns in the table

    def Filter1_1Changed(self):
        self.Filter1_QListWidget_1.clear()
        if not self.Filter1_ComboBox_1.currentText()=='':
            self.PopulateFilterList(self.table1,'Filter1_QListWidget_1', self.Filter1_ComboBox_1.currentText())  # For some reason it is not possible to send currentText with the SIGNAL-trigger
        
    def Filter2_1Changed(self):
        self.Filter2_QListWidget_1.clear()
        if not self.Filter2_ComboBox_1.currentText()=='':
            self.PopulateFilterList(self.table1,'Filter2_QListWidget_1', self.Filter2_ComboBox_1.currentText())  # For some reason it is not possible to send currentText with the SIGNAL-trigger

    def Filter1_2Changed(self):
        self.Filter1_QListWidget_2.clear()
        if not self.Filter1_ComboBox_2.currentText()=='':
            self.PopulateFilterList(self.table2,'Filter1_QListWidget_2', self.Filter1_ComboBox_2.currentText())  
            
    def Filter2_2Changed(self):
        self.Filter2_QListWidget_2.clear()
        if not self.Filter2_ComboBox_2.currentText()=='':
            self.PopulateFilterList(self.table2,'Filter2_QListWidget_2', self.Filter2_ComboBox_2.currentText())

    def Filter1_3Changed(self):
        self.Filter1_QListWidget_3.clear()
        if not self.Filter1_ComboBox_3.currentText()=='':
            self.PopulateFilterList(self.table3,'Filter1_QListWidget_3', self.Filter1_ComboBox_3.currentText())
        
    def Filter2_3Changed(self):
        self.Filter2_QListWidget_3.clear()
        if not self.Filter2_ComboBox_3.currentText()=='':
            self.PopulateFilterList(self.table3,'Filter2_QListWidget_3', self.Filter2_ComboBox_3.currentText())
                        
    def PopulateFilterList(self, table, QListWidgetname='', filtercolumn=None):
        sql = "select distinct " + unicode(filtercolumn) + " from " + table + " order by " + unicode(filtercolumn)
        list_data=sql_load_fr_db(self.database, sql)
        for post in list_data:
            item = QtGui.QListWidgetItem(unicode(post[0]))
            getattr(self, QListWidgetname).addItem(item)

    def storesettings(self):
        self.settings.setValue('db',self.database)
        self.settings.setValue('table1', self.table_ComboBox_1.currentText())
        self.settings.setValue('xcol1', self.xcol_ComboBox_1.currentText())
        self.settings.setValue('ycol1', self.ycol_ComboBox_1.currentText())
        self.table1=self.table_ComboBox_1.currentText()
        self.xcol1=self.xcol_ComboBox_1.currentText()
        self.ycol1=self.ycol_ComboBox_1.currentText()
        self.settings.setValue('table2', self.table_ComboBox_2.currentText())
        self.settings.setValue('xcol2', self.xcol_ComboBox_2.currentText())
        self.settings.setValue('ycol2', self.ycol_ComboBox_2.currentText())
        self.table2=self.table_ComboBox_2.currentText()
        self.xcol2=self.xcol_ComboBox_2.currentText()
        self.ycol2=self.ycol_ComboBox_2.currentText()
        self.settings.setValue('table3', self.table_ComboBox_3.currentText())
        self.settings.setValue('xcol3', self.xcol_ComboBox_3.currentText())
        self.settings.setValue('ycol3', self.ycol_ComboBox_3.currentText())
        self.table3=self.table_ComboBox_3.currentText()
        self.xcol3=self.xcol_ComboBox_3.currentText()
        self.ycol3=self.ycol_ComboBox_3.currentText()

    def readsettings(self): #only used when application starts, to load default values from last run
        if len((self.settings.value('db')).toString())>0:
            self.database = self.settings.value('db',type='QString')
            #print self.database
            self.openDBFile()

            try:#table1
                self.table1 = self.settings.value('table1').toString()
                notfound=0 
                i=0
                while notfound==0:    # Loop until the last selected table1 is found
                    self.table_ComboBox_1.setCurrentIndex(i)
                    if self.table_ComboBox_1.currentText() == self.table1: #The index count stops when last selected table is found
                        notfound=1
                        self.Table1Changed() # Fill xcol,ycol,filter1,filter2 comboboxes with info from selected table
                        try:#xcol1
                            self.xcol1 = self.settings.value('xcol1').toString()
                            notfound2=0 
                            j=0
                            while notfound2==0:    # loop until the last selected tscolumn is found
                                self.xcol_ComboBox_1.setCurrentIndex(j)
                                if self.xcol_ComboBox_1.currentText() == self.xcol1: # index count stops when column found
                                    notfound2=1
                                elif j> len(self.xcol_ComboBox_1):
                                    notfound2=1
                                j = j + 1
                        except:
                            print 'no stored data for xcolumn'
                        try:#ycol1
                            self.ycol1 = self.settings.value('ycol1').toString()
                            notfound2=0 
                            j=0
                            while notfound2==0:    # loop until the last selected tscolumn is found
                                self.ycol_ComboBox_1.setCurrentIndex(j)
                                if self.ycol_ComboBox_1.currentText() == self.ycol1: # index count stops when column found
                                    notfound2=1
                                elif j> len(self.ycol_ComboBox_1):
                                    notfound2=1
                                j = j + 1
                        except:
                            print 'no stored data for ycolumn'
                    elif i> len(self.table_ComboBox_1):
                        notfound=1
                    i = i + 1
            except:
                print 'nothing to be done for table1'

            try:#table2
                self.table2 = self.settings.value('table2').toString()
                notfound=0 
                i=0
                while notfound==0:    # Loop until the last selected table2 is found
                    self.table_ComboBox_2.setCurrentIndex(i)
                    if self.table_ComboBox_2.currentText() == self.table2: #The index count stops when last selected table is found
                        notfound=1
                        self.Table2Changed() # Fill xcol,ycol,filter1,filter2 comboboxes with info from selected table
                        try:#xcol2
                            self.xcol2 = self.settings.value('xcol2').toString()
                            notfound2=0 
                            j=0
                            while notfound2==0:    # loop until the last selected tscolumn is found
                                self.xcol_ComboBox_2.setCurrentIndex(j)
                                if self.xcol_ComboBox_2.currentText() == self.xcol2: # index count stops when column found
                                    notfound2=1
                                elif j> len(self.xcol_ComboBox_2):
                                    notfound2=1
                                j = j + 1
                        except:
                            print 'no stored data for xcolumn'
                        try:#ycol2
                            self.ycol2 = self.settings.value('ycol2').toString()
                            notfound2=0 
                            j=0
                            while notfound2==0:    # loop until the last selected tscolumn is found
                                self.ycol_ComboBox_2.setCurrentIndex(j)
                                if self.ycol_ComboBox_2.currentText() == self.ycol2: # index count stops when column found
                                    notfound2=1
                                elif j> len(self.ycol_ComboBox_2):
                                    notfound2=1
                                j = j + 1
                        except:
                            print 'no stored data for ycolumn'
                    elif i> len(self.table_ComboBox_2):
                        notfound=1
                    i = i + 1
            except:
                print 'nothing to be done for table2'

            try:#table3
                self.table3 = self.settings.value('table3').toString()
                notfound=0 
                i=0
                while notfound==0:    # Loop until the last selected table2 is found
                    self.table_ComboBox_3.setCurrentIndex(i)
                    if self.table_ComboBox_3.currentText() == self.table3: #The index count stops when last selected table is found
                        notfound=1
                        self.Table3Changed() # Fill xcol,ycol,filter1,filter2 comboboxes with info from selected table
                        try:#xcol3
                            self.xcol3 = self.settings.value('xcol3').toString()
                            notfound2=0 
                            j=0
                            while notfound2==0:    # loop until the last selected tscolumn is found
                                self.xcol_ComboBox_3.setCurrentIndex(j)
                                if self.xcol_ComboBox_3.currentText() == self.xcol3: # index count stops when column found
                                    notfound2=1
                                elif j> len(self.xcol_ComboBox_3):
                                    notfound2=1
                                j = j + 1
                        except:
                            print 'no stored data for xcolumn'
                        try:#ycol3
                            self.ycol3 = self.settings.value('ycol3').toString()
                            notfound2=0 
                            j=0
                            while notfound2==0:    # loop until the last selected tscolumn is found
                                self.ycol_ComboBox_3.setCurrentIndex(j)
                                if self.ycol_ComboBox_3.currentText() == self.ycol3: # index count stops when column found
                                    notfound2=1
                                elif j> len(self.ycol_ComboBox_3):
                                    notfound2=1
                                j = j + 1
                        except:
                            print 'no stored data for ycolumn'
                    elif i> len(self.table_ComboBox_3):
                        notfound=1
                    i = i + 1
            except:
                print 'nothing to be done for table3'
                
    def about(self):
        version = u'0.2.4'
        contact = u'groundwatergis@gmail.com'
        web = u'http://sourceforge.net/projects/plotsqlite'
        TEXT = 'This is PlotSQLite - the Midvatten plot generator.\n\nVersion: ' + version + '\nContact: ' + contact + '\nMore info: ' + web 
        QtGui.QMessageBox.information(None, "info", TEXT) 
        
                
def sql_load_fr_db(dbpath, sql=''):
    conn = sqlite.connect(unicode(dbpath),detect_types=sqlite.PARSE_DECLTYPES|sqlite.PARSE_COLNAMES)
    curs = conn.cursor()
    resultfromsql = curs.execute(unicode(sql)) #Send SQL-syntax to cursor
    result = resultfromsql.fetchall()
    resultfromsql.close()
    conn.close()
    return result
     
def main():
    app=QtGui.QApplication.instance() # checks if QApplication already exists 
    if not app: # create QApplication if it doesnt exist 
        app = QtGui.QApplication(sys.argv)     
        MainWindow()
    sys.exit(app.exec_())#comment out when using Ipython

if __name__ == "__main__":
    main()
